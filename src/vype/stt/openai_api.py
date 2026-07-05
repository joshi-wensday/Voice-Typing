"""OpenAI-compatible /v1/audio/transcriptions backend (cloud or self-hosted)."""

from __future__ import annotations

import io
import wave

import httpx
import numpy as np

from ..config import SttConfig

DEFAULT_MODEL = "whisper-1"
SAMPLE_RATE = 16000


def _to_wav_bytes(audio: np.ndarray) -> bytes:
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


class OpenAIAPITranscriber:
    def __init__(self, cfg: SttConfig, client: httpx.Client | None = None) -> None:
        self._cfg = cfg
        self._model = cfg.model or DEFAULT_MODEL
        self._client = client

    def load(self) -> None:
        if self._client is None:
            self._client = httpx.Client(base_url=self._cfg.base_url, timeout=30.0)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        if self._client is None:
            self.load()

        headers = {}
        if self._cfg.api_key:
            headers["Authorization"] = f"Bearer {self._cfg.api_key}"

        response = self._client.post(
            "/audio/transcriptions",
            files={"file": ("audio.wav", _to_wav_bytes(audio), "audio/wav")},
            data={"model": self._model},
            headers=headers,
        )
        response.raise_for_status()
        return response.json().get("text", "").strip()
