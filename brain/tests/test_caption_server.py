import asyncio
import json

import websockets

from brain.caption_server import start_server


async def test_forwards_received_caption_to_handler():
    received = []
    got_one = asyncio.Event()

    def on_caption(caption):
        received.append(caption)
        got_one.set()

    async with start_server("localhost", 8765, on_caption=on_caption, on_call_ended=lambda: None):
        async with websockets.connect("ws://localhost:8765") as client:
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
            await asyncio.wait_for(got_one.wait(), timeout=1.0)

    assert len(received) == 1
    assert received[0].speaker == "Alice"
    assert received[0].text == "こんにちは"
    assert received[0].timestamp == "2026-07-19T10:00:00Z"


async def test_forwards_call_ended_to_handler():
    got_ended = asyncio.Event()

    async with start_server(
        "localhost",
        8767,
        on_caption=lambda caption: None,
        on_call_ended=got_ended.set,
    ):
        async with websockets.connect("ws://localhost:8767") as client:
            await client.send(json.dumps({"type": "call_ended", "timestamp": "2026-07-19T10:05:00Z"}))
            await asyncio.wait_for(got_ended.wait(), timeout=1.0)
