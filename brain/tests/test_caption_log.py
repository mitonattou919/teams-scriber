import json

from brain.captions import Caption, CaptionLog


def test_append_writes_caption_as_jsonl_line(tmp_path):
    log_path = tmp_path / "captions.jsonl"
    log = CaptionLog(log_path)
    caption = Caption(speaker="Alice", text="hello", timestamp="2026-07-19T10:00:00+00:00")

    log.append(caption)

    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "speaker": "Alice",
        "text": "hello",
        "timestamp": "2026-07-19T10:00:00+00:00",
    }


def test_append_twice_appends_two_lines(tmp_path):
    log_path = tmp_path / "captions.jsonl"
    log = CaptionLog(log_path)

    log.append(Caption(speaker="Alice", text="first", timestamp="2026-07-19T10:00:00+00:00"))
    log.append(Caption(speaker="Bob", text="second", timestamp="2026-07-19T10:00:05+00:00"))

    lines = log_path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["text"] == "second"


def test_read_all_returns_captions_in_order(tmp_path):
    log_path = tmp_path / "captions.jsonl"
    log = CaptionLog(log_path)
    log.append(Caption(speaker="Alice", text="first", timestamp="2026-07-19T10:00:00+00:00"))
    log.append(Caption(speaker="Bob", text="second", timestamp="2026-07-19T10:00:05+00:00"))

    captions = log.read_all()

    assert captions == [
        Caption(speaker="Alice", text="first", timestamp="2026-07-19T10:00:00+00:00"),
        Caption(speaker="Bob", text="second", timestamp="2026-07-19T10:00:05+00:00"),
    ]


def test_read_all_returns_empty_list_when_file_missing(tmp_path):
    log = CaptionLog(tmp_path / "missing.jsonl")

    assert log.read_all() == []
