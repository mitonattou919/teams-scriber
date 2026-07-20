"""耳(ear/)からキャプション・会議終了通知をWebSocketで受信するサーバー。

耳側は resultType: 'Final' のキャプションのみを送信してくる(仕様上の前提)。
メッセージは {"type": "caption", ...} / {"type": "call_ended", ...} のいずれか。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import websockets
from dotenv import find_dotenv, load_dotenv

from brain.captions import Caption, CaptionBuffer, CaptionLog, build_caption_handler
from brain.llm import LLMClient, build_llm_client_from_env
from brain.minutes import generate_minutes, save_minutes

BUFFER_WINDOW = timedelta(minutes=10)


async def generate_and_save_minutes(
    log: CaptionLog, llm: LLMClient, minutes_dir: Path, meeting_id: str
) -> tuple[Path, Path]:
    """会議終了通知をトリガーに、全文ログから議事録を生成しMarkdown/JSONで保存する。"""
    captions = log.read_all()
    minutes = await generate_minutes(captions, llm)
    return save_minutes(minutes, minutes_dir, meeting_id=meeting_id, generated_at=datetime.now(timezone.utc))


def start_server(
    host: str,
    port: int,
    on_caption: Callable[[Caption], None],
    on_call_ended: Callable[[], None],
):
    async def handler(websocket) -> None:
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "caption":
                caption = Caption(
                    speaker=data["speaker"],
                    text=data["text"],
                    timestamp=data["timestamp"],
                )
                on_caption(caption)
            elif data["type"] == "call_ended":
                on_call_ended()

    return websockets.serve(handler, host, port)


def main() -> None:
    load_dotenv(find_dotenv())

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-path", default="captions.jsonl")
    parser.add_argument("--minutes-dir", default="minutes")
    args = parser.parse_args()

    buffer = CaptionBuffer(window=BUFFER_WINDOW)
    log = CaptionLog(Path(args.log_path))
    forward = build_caption_handler(buffer, log)
    meeting_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    minutes_generated = False

    def on_caption(caption: Caption) -> None:
        forward(caption)
        print(f"[brain] caption: {caption.speaker} {caption.text}", file=sys.stderr)

    async def handle_call_ended() -> None:
        nonlocal minutes_generated
        if minutes_generated:
            return
        minutes_generated = True
        print("[brain] call ended, generating minutes...", file=sys.stderr)
        try:
            llm = build_llm_client_from_env()
            md_path, json_path = await generate_and_save_minutes(
                log, llm, Path(args.minutes_dir), meeting_id
            )
            print(f"[brain] minutes saved: {md_path}, {json_path}", file=sys.stderr)
        except Exception as error:
            print(f"[brain] failed to generate minutes: {error}", file=sys.stderr)

    def on_call_ended() -> None:
        asyncio.create_task(handle_call_ended())

    async def run() -> None:
        async with start_server(args.host, args.port, on_caption, on_call_ended):
            print(
                f"[brain] caption server listening on ws://{args.host}:{args.port}, logging to {args.log_path}",
                file=sys.stderr,
            )
            await asyncio.Future()

    asyncio.run(run())


if __name__ == "__main__":
    main()
