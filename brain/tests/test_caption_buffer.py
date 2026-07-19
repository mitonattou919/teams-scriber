from datetime import datetime, timedelta, timezone

from brain.captions import Caption, CaptionBuffer


def test_recent_includes_added_caption():
    buffer = CaptionBuffer(window=timedelta(minutes=10))
    now = datetime(2026, 7, 19, 10, 0, 0, tzinfo=timezone.utc)
    caption = Caption(speaker="Alice", text="hello", timestamp=now.isoformat())

    buffer.add(caption, now=now)

    assert buffer.recent(now=now) == [caption]


def test_recent_excludes_captions_older_than_window():
    buffer = CaptionBuffer(window=timedelta(minutes=10))
    t0 = datetime(2026, 7, 19, 10, 0, 0, tzinfo=timezone.utc)
    old_caption = Caption(speaker="Alice", text="old", timestamp=t0.isoformat())
    buffer.add(old_caption, now=t0)

    later = t0 + timedelta(minutes=11)
    new_caption = Caption(speaker="Bob", text="new", timestamp=later.isoformat())
    buffer.add(new_caption, now=later)

    assert buffer.recent(now=later) == [new_caption]
