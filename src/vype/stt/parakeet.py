"""NVIDIA Parakeet TDT 0.6B v3 via onnx-asr — the default local engine.

~6.3% WER, tens-of-milliseconds inference on an RTX 3080, ~1.5 GB VRAM,
no NeMo dependency tree.
"""

from __future__ import annotations

import logging

import numpy as np

from ..config import SttConfig

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "nemo-parakeet-tdt-0.6b-v3"


class ParakeetTranscriber:
    def __init__(self, cfg: SttConfig) -> None:
        self._model_id = cfg.model or DEFAULT_MODEL
        self._device = cfg.device
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        import onnx_asr

        providers = None
        if self._device.lower() == "cuda":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        logger.info("Loading Parakeet model %s (device=%s)", self._model_id, self._device)
        try:
            self._model = onnx_asr.load_model(self._model_id, providers=providers)
        except TypeError:
            # older onnx-asr versions have no providers kwarg
            self._model = onnx_asr.load_model(self._model_id)
        logger.info("Parakeet model loaded")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        if self._model is None:
            self.load()
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        try:
            result = self._model.recognize(audio, sample_rate=16000)
        except TypeError:
            # older onnx-asr versions take the waveform only (assumes 16 kHz)
            result = self._model.recognize(audio)
        return (result or "").strip()
