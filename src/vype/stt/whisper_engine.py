"""Whisper STT engine integration using faster-whisper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from ..config.manager import ConfigManager
from .text_processor import TextProcessor


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
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = str(language) if language is not None else None
        self._model: WhisperModel | None = None
        self._cfgm = ConfigManager()
        
        # Initialize text processor with config settings
        self._text_processor = TextProcessor(
            remove_fillers=self._cfgm.config.stt.remove_filler_words,
            improve_grammar=self._cfgm.config.stt.improve_grammar
        )

    def _init_model(self, compute_type: str | None = None) -> None:
        ct = compute_type or self.compute_type
        self._model = WhisperModel(self.model_name, device=self.device, compute_type=ct)
        self.compute_type = ct

    def preload(self) -> None:
        if self._model is not None:
            return
        try:
            self._init_model()
        except ValueError as e:
            if "float16" in str(e):
                self._init_model("float32")
            else:
                raise

    def load_model(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self.preload()

    def get_supported_models(self) -> list[str]:
        return ["tiny", "base", "small", "medium", "large-v2"]

    def _decode_params(self) -> dict:
        d = self._cfgm.config.decoding
        return {
            "beam_size": d.beam_size,
            "temperature": d.temperature,
            # faster-whisper uses initial_prompt; condition_on_previous_text is implicitly handled by context
        }

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        if audio_data.ndim != 1:
            raise ValueError("audio_data must be 1-D mono float32 array")
        if self._model is None:
            self.preload()
        assert self._model is not None
        segments, info = self._model.transcribe(
            audio=audio_data,
            language=self.language,
            vad_filter=True,
            **self._decode_params(),
        )
        text_parts = [seg.text for seg in segments]  # type: ignore[attr-defined]
        text = " ".join([t.strip() for t in text_parts]).strip()
        
        # Apply text processing (filler removal, grammar improvement)
        text = self._text_processor.process(text)
        
        return TranscriptionResult(text=text, language=getattr(info, "language", None))

    def transcribe_incremental(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        initial_prompt: str | None = None,
    ) -> str:
        if audio_data.size == 0:
            return ""
        if self._model is None:
            self.preload()
        assert self._model is not None
        segments, _ = self._model.transcribe(
            audio=audio_data,
            language=self.language,
            vad_filter=True,
            initial_prompt=initial_prompt,
            **self._decode_params(),
        )
        text_parts = [seg.text for seg in segments]  # type: ignore[attr-defined]
        text = " ".join([t.strip() for t in text_parts]).strip()
        
        # Apply text processing (filler removal, grammar improvement)
        text = self._text_processor.process(text)
        
        return text
