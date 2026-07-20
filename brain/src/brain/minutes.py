"""会議全文ログから議事録(決定事項・宿題・担当・期限)を構造化生成する。

判定・生成ロジック(このモジュール)とLLM呼び出し(brain.llm)は分離してあり、
このモジュールは `LLMClient.complete()` のみに依存する。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from brain.captions import Caption
from brain.llm import LLMClient

SYSTEM_PROMPT = (
    "あなたは会議の議事録作成者です。与えられた会議の発言ログ全文から、"
    "決定事項と宿題(担当者・期限つきのアクションアイテム)を抽出してください。\n"
    "出力は次のJSON形式のみとし、説明文やコードブロックは付けないでください。\n"
    '{"decisions": ["決定事項の文"], '
    '"action_items": [{"task": "やること", "owner": "担当者またはnull", "due": "期限またはnull"}]}\n'
    "発言から担当者・期限が読み取れない項目は owner / due を null にしてください。"
    "決定事項・宿題が存在しない場合は空配列にしてください。"
)


@dataclass(frozen=True)
class ActionItem:
    task: str
    owner: str | None
    due: str | None


@dataclass(frozen=True)
class Minutes:
    decisions: list[str]
    action_items: list[ActionItem]


def build_transcript(captions: list[Caption]) -> str:
    return "\n".join(f"[{c.timestamp}] {c.speaker}: {c.text}" for c in captions)


async def generate_minutes(captions: list[Caption], llm: LLMClient) -> Minutes:
    transcript = build_transcript(captions)
    raw = await llm.complete(system=SYSTEM_PROMPT, user=transcript)
    data = json.loads(raw)
    action_items = [
        ActionItem(task=item["task"], owner=item.get("owner"), due=item.get("due"))
        for item in data.get("action_items", [])
    ]
    return Minutes(decisions=list(data.get("decisions", [])), action_items=action_items)


def save_minutes(
    minutes: Minutes, out_dir: Path, meeting_id: str, generated_at: datetime
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{meeting_id}.md"
    json_path = out_dir / f"{meeting_id}.json"

    json_path.write_text(
        json.dumps(
            {
                "meeting_id": meeting_id,
                "generated_at": generated_at.isoformat(),
                "decisions": minutes.decisions,
                "action_items": [asdict(item) for item in minutes.action_items],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [f"# 議事録 ({generated_at.isoformat()})", "", "## 決定事項"]
    lines += [f"- {d}" for d in minutes.decisions] if minutes.decisions else ["- (なし)"]
    lines += ["", "## 宿題"]
    if minutes.action_items:
        for item in minutes.action_items:
            owner = item.owner or "未定"
            due = item.due or "未定"
            lines.append(f"- [ ] {item.task} (担当: {owner}, 期限: {due})")
    else:
        lines.append("- (なし)")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return md_path, json_path
