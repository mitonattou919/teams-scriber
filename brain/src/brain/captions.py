"""キャプションのドメインモデル。"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Caption:
    speaker: str
    text: str
    timestamp: str  # ISO 8601


class CaptionBuffer:
    """直近 `window` ぶんのキャプションのみを保持するバッファ。"""

    def __init__(self, window: timedelta) -> None:
        self._window = window
        self._items: deque[tuple[datetime, Caption]] = deque()

    def add(self, caption: Caption, now: datetime) -> None:
        self._items.append((now, caption))
        self._evict(now)

    def recent(self, now: datetime) -> list[Caption]:
        self._evict(now)
        return [caption for _, caption in self._items]

    def _evict(self, now: datetime) -> None:
        cutoff = now - self._window
        while self._items and self._items[0][0] < cutoff:
            self._items.popleft()


class CaptionLog:
    """会議全体のキャプションをJSONLとしてローカルに逐次追記保存する。

    10分ウィンドウの `CaptionBuffer` とは独立に全件保持する(将来の議事録生成の入力になるため)。
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, caption: Caption) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(caption), ensure_ascii=False))
            f.write("\n")

    def read_all(self) -> list[Caption]:
        """会議終了時の議事録生成の入力として、保存済みの全文ログを読み込む。"""
        if not self._path.exists():
            return []
        captions = []
        with self._path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                captions.append(Caption(**data))
        return captions


def build_caption_handler(
    buffer: CaptionBuffer, log: CaptionLog
) -> Callable[[Caption], None]:
    """受信したキャプションをバッファへの追加と全文ログへの追記の両方に流す。"""

    def on_caption(caption: Caption) -> None:
        buffer.add(caption, now=datetime.now(timezone.utc))
        log.append(caption)

    return on_caption
