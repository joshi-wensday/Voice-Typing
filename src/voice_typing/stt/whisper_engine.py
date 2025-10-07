"""Whisper STT engine integration using faster-whisper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
from faster_whisper import WhisperModel


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = None


class FasterWhisperEngine:
    """Wrapper around faster-whisper WhisperModel."""

    def __init__(
        self,
        model: str = "base",
        device: str = "auto",
        compute_type: str = "float16",
        language: str | None = "en",
    ) -> None:
        """Initialize the engine.

        Args:
            model: Whisper model size/name
            device: Device selection (auto, cuda, cpu)
            compute_type: Inference precision (float16, int8, float32)
            language: ISO language code or None for auto-detect
        """
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = str(language) if language is not None else None
        self._model: WhisperModel | None = None

    def _init_model(self, compute_type: str | None = None) -> None:
        ct = compute_type or self.compute_type
        self._model = WhisperModel(self.model_name, device=self.device, compute_type=ct)
        self.compute_type = ct

    def preload(self) -> None:
        """Load the Whisper model into memory, with float32 fallback if needed."""
        if self._model is not None:
            return
        try:
            self._init_model()
        except ValueError as e:
            # Fallback if float16 unsupported
            if "float16" in str(e):
                self._init_model("float32")
            else:
                raise

    def load_model(self, model_name: str) -> None:
        """Swap the model at runtime."""
        self.model_name = model_name
        # Force reload
        self._model = None
        self.preload()

    def get_supported_models(self) -> list[str]:
        """Return common model names."""
        return ["tiny", "base", "small", "medium", "large-v2"]

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe mono float32 audio to text (batch)."""
        if audio_data.ndim != 1:
            raise ValueError("audio_data must be 1-D mono float32 array")
        if self._model is None:
            self.preload()
        assert self._model is not None
        segments, info = self._model.transcribe(
            audio=audio_data,
            language=self.language,
            vad_filter=False,
            beam_size=1,
        )
        text_parts = [seg.text for seg in segments]  # type: ignore[attr-defined]
        text = " ".join([t.strip() for t in text_parts]).strip()
        return TranscriptionResult(text=text, language=getattr(info, "language", None))

    def transcribe_incremental(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe short chunks to support streaming.

        Note: This is a naive approach that runs decode per chunk. For
a higher-performance streaming solution, integrate VAD and segment caching.
        """
        if audio_data.size == 0:
            return ""
        return self.transcribe(audio_data, sample_rate=sample_rate).text
