"""History: append-only JSONL with rotation and last-record lookup."""

import json

from vype.history import History


def test_append_writes_jsonl(tmp_path):
    h = History(tmp_path / "history.jsonl")
    h.append(raw="hello world")
    h.append(raw="second", cleaned="Second.")
    lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec0 = json.loads(lines[0])
    assert rec0["raw"] == "hello world"
    assert rec0["cleaned"] is None
    assert "ts" in rec0
    rec1 = json.loads(lines[1])
    assert rec1["cleaned"] == "Second."


def test_last_returns_most_recent(tmp_path):
    h = History(tmp_path / "history.jsonl")
    assert h.last() is None
    h.append(raw="a")
    h.append(raw="b")
    assert h.last()["raw"] == "b"


def test_last_text_prefers_cleaned(tmp_path):
    h = History(tmp_path / "history.jsonl")
    h.append(raw="raw text", cleaned="Clean text.")
    assert h.last_text() == "Clean text."
    h.append(raw="only raw")
    assert h.last_text() == "only raw"


def test_rotation_when_file_exceeds_max_bytes(tmp_path):
    path = tmp_path / "history.jsonl"
    h = History(path, max_bytes=200)
    for i in range(20):
        h.append(raw=f"utterance number {i} padded out to take some space")
    assert path.exists()
    assert (tmp_path / "history.1.jsonl").exists()
    # current file stays under the cap plus one record
    assert path.stat().st_size < 400


def test_recent_returns_newest_first(tmp_path):
    h = History(tmp_path / "history.jsonl")
    for i in range(5):
        h.append(raw=f"utterance {i}")
    recent = h.recent(3)
    assert [r["raw"] for r in recent] == ["utterance 4", "utterance 3", "utterance 2"]


def test_recent_on_empty_history(tmp_path):
    h = History(tmp_path / "history.jsonl")
    assert h.recent(5) == []


def test_delete_removes_matching_record(tmp_path):
    h = History(tmp_path / "history.jsonl")
    h.append(raw="keep me")
    h.append(raw="delete me")
    h.append(raw="keep me too")
    target = h.recent(3)[1]  # "delete me"
    assert h.delete(target["ts"]) is True
    remaining = [r["raw"] for r in h.recent(10)]
    assert remaining == ["keep me too", "keep me"]


def test_delete_unknown_ts_returns_false(tmp_path):
    h = History(tmp_path / "history.jsonl")
    h.append(raw="something")
    assert h.delete(12345.0) is False
    assert len(h.recent(10)) == 1


def test_clear_removes_all_records_and_rotated_file(tmp_path):
    path = tmp_path / "history.jsonl"
    h = History(path, max_bytes=200)
    for i in range(20):  # forces rotation
        h.append(raw=f"utterance number {i} padded out to take some space")
    h.clear()
    assert not path.exists()
    assert not (tmp_path / "history.1.jsonl").exists()
    assert h.recent(10) == []
    assert h.last() is None


def test_unicode_roundtrip(tmp_path):
    h = History(tmp_path / "history.jsonl")
    h.append(raw="naïve café — ✨")
    assert h.last()["raw"] == "naïve café — ✨"
