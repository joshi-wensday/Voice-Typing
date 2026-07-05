"""NotesStore: persistent capture inbox (unlike dictation history, never auto-wiped)."""

from vype.notes import NotesStore


def test_add_and_recent(tmp_path):
    store = NotesStore(tmp_path / "notes.jsonl")
    store.add("first thought")
    store.add("second thought", source="siri", tags=["podcast"])
    notes = store.recent(10)
    assert [n["text"] for n in notes] == ["second thought", "first thought"]
    assert notes[0]["source"] == "siri"
    assert notes[0]["tags"] == ["podcast"]
    assert notes[1]["source"] == "app"


def test_recent_respects_limit(tmp_path):
    store = NotesStore(tmp_path / "notes.jsonl")
    for i in range(5):
        store.add(f"n{i}")
    assert len(store.recent(3)) == 3


def test_persists_across_instances(tmp_path):
    NotesStore(tmp_path / "notes.jsonl").add("durable")
    assert NotesStore(tmp_path / "notes.jsonl").recent(1)[0]["text"] == "durable"


def test_empty_store(tmp_path):
    assert NotesStore(tmp_path / "notes.jsonl").recent(5) == []
