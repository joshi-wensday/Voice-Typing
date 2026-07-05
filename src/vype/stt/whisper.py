"""faster-whisper large-v3-turbo — the multilingual local alternative."""

from __future__ import annotations

import logging

import numpy as np

from ..config import SttConfig

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "large-v3-turbo"


class WhisperTranscriber:
    def __init__(self, cfg: SttConfig) -> None:
        self._model_id = cfg.model or DEFAULT_MODEL
        self._device = cfg.device
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        compute_type = "float16" if self._device.lower() == "cuda" else "int8"
        logger.info("Loading faster-whisper %s (device=%s)", self._model_id, self._device)
        self._model = WhisperModel(self._model_id, device=self._device, compute_type=compute_type)
        logger.info("faster-whisper model loaded")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        if self._model is None:
            self.load()
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        segments, _info = self._model.transcribe(audio, vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segments).strip()
