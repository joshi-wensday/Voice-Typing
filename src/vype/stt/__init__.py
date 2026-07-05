"""STT backends behind one protocol. Local vs API is a config change, not code."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ..config import SttConfig


@runtime_checkable
class Transcriber(Protocol):
    def load(self) -> None:
        """Load model / open client. Called once at startup; must be idempotent."""
        ...

    def transcribe(self, audio: np.ndarray) -> str:
        """16 kHz mono float32 in, plain text out. Empty audio → empty string."""
        ...


def create_transcriber(cfg: SttConfig) -> Transcriber:
    backend = cfg.backend.lower().strip()
    if backend == "parakeet":
        from . import parakeet

        return parakeet.ParakeetTranscriber(cfg)
    if backend == "whisper":
        from . import whisper

        return whisper.WhisperTranscriber(cfg)
    if backend == "openai":
        if not cfg.base_url:
            raise ValueError("stt.base_url is required for the openai backend")
        from . import openai_api

        return openai_api.OpenAIAPITranscriber(cfg)
    raise ValueError(f"Unknown STT backend: {cfg.backend!r} (expected parakeet | whisper | openai)")
