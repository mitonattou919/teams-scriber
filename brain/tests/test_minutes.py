import json
from datetime import datetime, timezone

from brain.captions import Caption
from brain.minutes import ActionItem, Minutes, build_transcript, generate_minutes, save_minutes


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict] = []

    async def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self.response


def test_build_transcript_includes_speaker_timestamp_and_text():
    captions = [
        Caption(speaker="Alice", text="こんにちは", timestamp="2026-07-19T10:00:00Z"),
        Caption(speaker="Bob", text="よろしくお願いします", timestamp="2026-07-19T10:00:05Z"),
    ]

    transcript = build_transcript(captions)

    assert "Alice" in transcript
    assert "こんにちは" in transcript
    assert "2026-07-19T10:00:00Z" in transcript
    assert transcript.index("Alice") < transcript.index("Bob")


async def test_generate_minutes_parses_llm_json_response():
    llm = FakeLLMClient(
        json.dumps(
            {
                "decisions": ["来週リリースする"],
                "action_items": [
                    {"task": "資料を送る", "owner": "田中", "due": "7/25"},
                    {"task": "議事録を確認する", "owner": None, "due": None},
                ],
            }
        )
    )
    captions = [Caption(speaker="Alice", text="来週リリースしましょう", timestamp="2026-07-19T10:00:00Z")]

    minutes = await generate_minutes(captions, llm)

    assert minutes.decisions == ["来週リリースする"]
    assert minutes.action_items == [
        ActionItem(task="資料を送る", owner="田中", due="7/25"),
        ActionItem(task="議事録を確認する", owner=None, due=None),
    ]
    assert len(llm.calls) == 1
    assert "Alice" in llm.calls[0]["user"]


def test_save_minutes_writes_markdown_and_json(tmp_path):
    minutes = Minutes(
        decisions=["来週リリースする"],
        action_items=[ActionItem(task="資料を送る", owner="田中", due="7/25")],
    )
    generated_at = datetime(2026, 7, 20, 10, 0, 0, tzinfo=timezone.utc)

    md_path, json_path = save_minutes(minutes, tmp_path, meeting_id="20260720T100000Z", generated_at=generated_at)

    assert md_path.exists()
    assert json_path.exists()

    md_text = md_path.read_text(encoding="utf-8")
    assert "来週リリースする" in md_text
    assert "資料を送る" in md_text
    assert "田中" in md_text
    assert "7/25" in md_text

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["meeting_id"] == "20260720T100000Z"
    assert data["decisions"] == ["来週リリースする"]
    assert data["action_items"] == [{"task": "資料を送る", "owner": "田中", "due": "7/25"}]


def test_save_minutes_handles_empty_minutes(tmp_path):
    minutes = Minutes(decisions=[], action_items=[])
    generated_at = datetime(2026, 7, 20, 10, 0, 0, tzinfo=timezone.utc)

    md_path, _ = save_minutes(minutes, tmp_path, meeting_id="empty", generated_at=generated_at)

    assert "(なし)" in md_path.read_text(encoding="utf-8")
