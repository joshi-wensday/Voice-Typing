"""Whisper STT engine integration using faster-whisper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]

from ..config.manager import ConfigManager
from .text_processor import TextProcessor


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = None


# V2: large-v3 is now the recommended default
_SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]


class FasterWhisperEngine:
    """Wrapper around faster-whisper WhisperModel.

    V2 changes:
    - large-v3 is included in supported models and is the default
    - compute_type defaults to float16 for CUDA throughput
    - transcribe_incremental accepts an externally managed initial_prompt
      (provided by ContextSummarizer) instead of the raw 120-char text tail
    - Internal TextProcessor filler/grammar passes are superseded by the
      Refiner skill, but are retained as a lightweight local fallback
    """

    def __init__(
        self,
        model: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str | None = "en",
    ) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = str(language) if language is not None else None
        self._model: WhisperModel | None = None
        self._cfgm = ConfigManager()

        # Lightweight local text processor (filler removal only; grammar handled by Refiner)
        self._text_processor = TextProcessor(
            remove_fillers=self._cfgm.config.stt.remove_filler_words,
            improve_grammar=False,  # V2: delegated to Refiner skill
        )

    def _init_model(self, compute_type: str | None = None) -> None:
        if WhisperModel is None:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Switch to the Canary backend (stt.backend: nemo) or reinstall faster-whisper."
            )
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
                # CPU fallback — float16 not supported without CUDA
                self._init_model("float32")
            else:
                raise

    def load_model(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self.preload()

    def get_supported_models(self) -> list[str]:
        return _SUPPORTED_MODELS

    def _decode_params(self) -> dict:
        d = self._cfgm.config.decoding
        return {
            "beam_size": d.beam_size,
            "temperature": d.temperature,
            "condition_on_previous_text": d.condition_on_previous_text,
            "log_prob_threshold": d.log_prob_threshold,
            "compression_ratio_threshold": d.compression_ratio_threshold,
            "no_speech_threshold": d.no_speech_threshold,
            "patience": d.patience,
            "repetition_penalty": d.repetition_penalty,
        }

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe a complete audio buffer.

        Args:
            audio_data: 1-D mono float32 array
            sample_rate: Sample rate in Hz (must be 16000 for Whisper)

        Returns:
            TranscriptionResult with cleaned text and detected language
        """
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
        text = self._text_processor.process(text)
        return TranscriptionResult(text=text, language=getattr(info, "language", None))

    def transcribe_incremental(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        initial_prompt: str | None = None,
    ) -> str:
        """Transcribe a VAD-confirmed speech segment with context injection.

        Called by the controller with an `initial_prompt` sourced from the
        rolling context tail.  vad_filter is explicitly disabled because the
        segment has already been pre-filtered by SileroVADSegmenter — a second
        pass would clip word onsets and degrade accuracy.

        Args:
            audio_data: 1-D mono float32 speech segment
            sample_rate: Must be 16000
            initial_prompt: Optional keyword/context string from ContextSummarizer

        Returns:
            Raw transcription text (before Refiner skill processing)
        """
        if audio_data.size == 0:
            return ""
        if self._model is None:
            self.preload()
        assert self._model is not None

        transcribe_kwargs = dict(
            audio=audio_data,
            language=self.language,
            # vad_filter is intentionally False here: the segment has already been
            # pre-filtered by SileroVADSegmenter before reaching this method.
            # Enabling it again runs Whisper's internal VAD on top of already-clean
            # audio and shaves 40-80ms off word onsets, causing consonant clipping.
            vad_filter=False,
            **self._decode_params(),
        )
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt

        segments, _ = self._model.transcribe(**transcribe_kwargs)  # type: ignore[arg-type]
        text_parts = [seg.text for seg in segments]  # type: ignore[attr-defined]
        text = " ".join([t.strip() for t in text_parts]).strip()

        # Minimal local processing (no grammar — handled downstream by Refiner)
        text = self._text_processor.process(text)
        return text
