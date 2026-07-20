import asyncio
import json
from datetime import datetime, timedelta, timezone

import websockets

from brain.caption_server import generate_and_save_minutes, start_server
from brain.captions import Caption, CaptionBuffer, CaptionLog, build_caption_handler


async def test_server_forwards_captions_to_buffer_and_log(tmp_path):
    buffer = CaptionBuffer(window=timedelta(minutes=10))
    log = CaptionLog(tmp_path / "captions.jsonl")
    on_caption = build_caption_handler(buffer, log)

    async with start_server("localhost", 8766, on_caption=on_caption, on_call_ended=lambda: None):
        async with websockets.connect("ws://localhost:8766") as client:
            await client.send(
                json.dumps(
                    {
                        "type": "caption",
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


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response

    async def complete(self, *, system: str, user: str) -> str:
        return self.response


async def test_generate_and_save_minutes_reads_log_and_writes_files(tmp_path):
    log = CaptionLog(tmp_path / "captions.jsonl")
    log.append(Caption(speaker="Alice", text="来週リリースしましょう", timestamp="2026-07-19T10:00:00Z"))
    llm = FakeLLMClient(json.dumps({"decisions": ["来週リリースする"], "action_items": []}))

    md_path, json_path = await generate_and_save_minutes(
        log, llm, tmp_path / "minutes", meeting_id="20260719T100500Z"
    )

    assert md_path.exists()
    assert json_path.exists()
    assert "来週リリースする" in md_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["decisions"] == ["来週リリースする"]
