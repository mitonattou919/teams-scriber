import asyncio
import json
from datetime import datetime, timedelta, timezone

import websockets

from brain.caption_server import start_server
from brain.captions import CaptionBuffer, CaptionLog, build_caption_handler


async def test_server_forwards_captions_to_buffer_and_log(tmp_path):
    buffer = CaptionBuffer(window=timedelta(minutes=10))
    log = CaptionLog(tmp_path / "captions.jsonl")
    on_caption = build_caption_handler(buffer, log)

    async with start_server("localhost", 8766, on_caption=on_caption):
        async with websockets.connect("ws://localhost:8766") as client:
            await client.send(
                json.dumps(
                    {
                        "speaker": "Alice",
                        "text": "こんにちは",
                        "resultType": "Final",
                        "timestamp": "2026-07-19T10:00:00Z",
                    }
                )
            )
            for _ in range(20):
                if (tmp_path / "captions.jsonl").exists():
                    break
                await asyncio.sleep(0.05)

    recent = buffer.recent(now=datetime.now(timezone.utc))
    assert len(recent) == 1
    assert recent[0].speaker == "Alice"

    lines = (tmp_path / "captions.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["speaker"] == "Alice"
