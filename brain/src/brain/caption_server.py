"""耳(ear/)からキャプションをWebSocketで受信するサーバー。

耳側は resultType: 'Final' のキャプションのみを送信してくる(仕様上の前提)。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Callable

import websockets

from brain.captions import Caption, CaptionBuffer, CaptionLog, build_caption_handler

BUFFER_WINDOW = timedelta(minutes=10)


def start_server(host: str, port: int, on_caption: Callable[[Caption], None]):
    async def handler(websocket) -> None:
        async for message in websocket:
            data = json.loads(message)
            caption = Caption(
                speaker=data["speaker"],
                text=data["text"],
                timestamp=data["timestamp"],
            )
            on_caption(caption)

    return websockets.serve(handler, host, port)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-path", default="captions.jsonl")
    args = parser.parse_args()

    buffer = CaptionBuffer(window=BUFFER_WINDOW)
    log = CaptionLog(Path(args.log_path))
    forward = build_caption_handler(buffer, log)

    def on_caption(caption: Caption) -> None:
        forward(caption)
        print(f"[brain] caption: {caption.speaker} {caption.text}", file=sys.stderr)

    async def run() -> None:
        async with start_server(args.host, args.port, on_caption):
            print(
                f"[brain] caption server listening on ws://{args.host}:{args.port}, logging to {args.log_path}",
                file=sys.stderr,
            )
            await asyncio.Future()

    asyncio.run(run())


if __name__ == "__main__":
    main()
