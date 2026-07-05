"""STT factory + OpenAI-compatible API backend (the only unit-testable backend).

Parakeet / faster-whisper backends are exercised by integration tests
(pytest -m gpu) — here we only verify the factory routes to them lazily.
"""

import io
import wave

import httpx
import numpy as np
import pytest

from vype.config import SttConfig
from vype.stt import create_transcriber
from vype.stt.openai_api import OpenAIAPITranscriber


def test_factory_unknown_backend_raises():
    with pytest.raises(ValueError, match="nope"):
        create_transcriber(SttConfig(backend="nope"))


def test_factory_routes_parakeet(monkeypatch):
    import vype.stt.parakeet as parakeet_mod

    class Marker:
        def __init__(self, cfg):
            self.cfg = cfg

    monkeypatch.setattr(parakeet_mod, "ParakeetTranscriber", Marker)
    t = create_transcriber(SttConfig(backend="parakeet"))
    assert isinstance(t, Marker)


def test_factory_routes_whisper(monkeypatch):
    import vype.stt.whisper as whisper_mod

    class Marker:
        def __init__(self, cfg):
            self.cfg = cfg

    monkeypatch.setattr(whisper_mod, "WhisperTranscriber", Marker)
    t = create_transcriber(SttConfig(backend="whisper"))
    assert isinstance(t, Marker)


def test_factory_routes_openai():
    cfg = SttConfig(backend="openai", base_url="http://x/v1", api_key="k")
    t = create_transcriber(cfg)
    assert isinstance(t, OpenAIAPITranscriber)


def test_openai_backend_requires_base_url():
    with pytest.raises(ValueError, match="base_url"):
        create_transcriber(SttConfig(backend="openai"))


# ── OpenAI API backend ───────────────────────────────────────────────────────

def make_api_transcriber(handler, **overrides):
    cfg = SttConfig(backend="openai", base_url="http://test/v1", api_key="sk-1", **overrides)
    transport = httpx.MockTransport(handler)
    t = OpenAIAPITranscriber(cfg, client=httpx.Client(transport=transport, base_url=cfg.base_url))
    t.load()
    return t


def test_api_transcribe_posts_wav_and_returns_text():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["content"] = request.read()
        return httpx.Response(200, json={"text": "hello world"})

    t = make_api_transcriber(handler)
    audio = np.zeros(16000, dtype=np.float32)  # 1 s of silence
    assert t.transcribe(audio) == "hello world"

    assert captured["url"].endswith("/audio/transcriptions")
    assert captured["auth"] == "Bearer sk-1"
    # multipart body contains a valid 16 kHz mono PCM-16 WAV
    body = captured["content"]
    wav_start = body.find(b"RIFF")
    assert wav_start != -1
    wav_bytes = body[wav_start:]
    with wave.open(io.BytesIO(wav_bytes[: wav_bytes.rfind(b"\r\n--")]), "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2


def test_api_transcribe_empty_audio_returns_empty_without_call():
    def handler(request):  # pragma: no cover
        raise AssertionError("no HTTP call expected")

    t = make_api_transcriber(handler)
    assert t.transcribe(np.zeros(0, dtype=np.float32)) == ""


def test_api_transcribe_error_raises():
    t = make_api_transcriber(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(Exception):
        t.transcribe(np.zeros(16000, dtype=np.float32))
