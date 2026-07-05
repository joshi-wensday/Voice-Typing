"""vype serve: transcription + notes API (FastAPI TestClient, FakeTranscriber)."""

import io
import wave

import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from vype.notes import NotesStore
from vype.server import create_app

TOKEN = "test-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeTranscriber:
    def __init__(self, text="hello from the phone"):
        self.text = text
        self.calls = []

    def load(self):
        pass

    def transcribe(self, audio):
        self.calls.append(audio)
        return self.text


def wav_bytes(seconds=1.0, sample_rate=16000, value=0.1):
    samples = np.full(int(seconds * sample_rate), value, dtype=np.float32)
    pcm = (samples * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


@pytest.fixture()
def api(tmp_path):
    transcriber = FakeTranscriber()
    notes = NotesStore(tmp_path / "notes.jsonl")
    app = create_app(transcriber=transcriber, notes=notes, token=TOKEN)
    client = TestClient(app)
    return client, transcriber, notes


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_missing_token_rejected(api):
    client, _, _ = api
    assert client.get("/notes").status_code == 401
    assert client.post("/notes", json={"text": "x"}).status_code == 401


def test_wrong_token_rejected(api):
    client, _, _ = api
    r = client.get("/notes", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_health_needs_no_token(api):
    client, _, _ = api
    assert client.get("/health").json()["status"] == "ok"


# ── Transcription ────────────────────────────────────────────────────────────

def test_transcribe_wav(api):
    client, transcriber, _ = api
    r = client.post(
        "/v1/audio/transcriptions",
        files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["text"] == "hello from the phone"
    audio = transcriber.calls[0]
    assert audio.dtype == np.float32
    assert len(audio) == 16000


def test_transcribe_resamples_non_16k(api):
    client, transcriber, _ = api
    r = client.post(
        "/v1/audio/transcriptions",
        files={"file": ("clip.wav", wav_bytes(seconds=1.0, sample_rate=48000), "audio/wav")},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert len(transcriber.calls[0]) == pytest.approx(16000, abs=2)


def test_transcribe_rejects_non_wav(api):
    client, _, _ = api
    r = client.post(
        "/v1/audio/transcriptions",
        files={"file": ("clip.mp4", b"not a wav", "audio/mp4")},
        headers=AUTH,
    )
    assert r.status_code == 400


# ── Notes ────────────────────────────────────────────────────────────────────

def test_note_roundtrip(api):
    client, _, _ = api
    r = client.post("/notes", json={"text": "capture me", "source": "siri"}, headers=AUTH)
    assert r.status_code == 200
    listing = client.get("/notes", headers=AUTH).json()
    assert len(listing["notes"]) == 1
    assert listing["notes"][0]["text"] == "capture me"
    assert listing["notes"][0]["source"] == "siri"
    assert "ts" in listing["notes"][0]


def test_notes_newest_first_with_limit(api):
    client, _, _ = api
    for i in range(5):
        client.post("/notes", json={"text": f"note {i}"}, headers=AUTH)
    listing = client.get("/notes?limit=2", headers=AUTH).json()
    assert [n["text"] for n in listing["notes"]] == ["note 4", "note 3"]


def test_empty_note_rejected(api):
    client, _, _ = api
    assert client.post("/notes", json={"text": "  "}, headers=AUTH).status_code == 400
