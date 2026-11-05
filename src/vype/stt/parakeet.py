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


def _find_sessions(obj, depth: int = 0, seen: set | None = None):
    """Walk onnx-asr's adapter/model objects for InferenceSessions (it keeps
    them in private attributes, nested a few levels deep)."""
    import onnxruntime

    seen = set() if seen is None else seen
    if id(obj) in seen or depth > 4:
        return
    seen.add(id(obj))
    if isinstance(obj, onnxruntime.InferenceSession):
        yield obj
        return
    if isinstance(obj, (list, tuple, set)):
        children = list(obj)
    elif isinstance(obj, dict):
        children = list(obj.values())
    elif hasattr(obj, "__dict__") and type(obj).__module__.startswith(("onnx_asr", "onnxruntime")):
        children = list(vars(obj).values())
    else:
        return
    for child in children:
        yield from _find_sessions(child, depth + 1, seen)


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
            import onnxruntime

            try:
                # picks up CUDA/cuDNN DLLs from the nvidia-*-cu12 pip wheels,
                # so no system-wide CUDA install is needed
                onnxruntime.preload_dlls()
            except Exception as exc:
                logger.warning("CUDA DLL preload failed (%s) — may fall back to CPU", exc)
            # requesting a provider the runtime doesn't have raises — filter to
            # what's actually available (CPU-only installs run fine, ~same speed)
            available = set(onnxruntime.get_available_providers())
            providers = [
                p
                for p in ("CUDAExecutionProvider", "CPUExecutionProvider")
                if p in available
            ] or None
            if "CUDAExecutionProvider" not in available:
                logger.info("CUDA provider not available — using CPU inference")
            else:
                logger.info("CUDA provider available — GPU inference enabled")
        logger.info("Loading Parakeet model %s (device=%s)", self._model_id, self._device)
        try:
            self._model = onnx_asr.load_model(self._model_id, providers=providers)
        except TypeError:
            # older onnx-asr versions have no providers kwarg
            self._model = onnx_asr.load_model(self._model_id)
        logger.info("Parakeet model loaded")

    def on_gpu(self) -> bool | None:
        """Is every ONNX session actually running on CUDA? Call after a warm-up
        transcribe: onnxruntime only discovers a broken cuDNN on the first run,
        then silently re-creates that session on CPU. None = not applicable
        (CPU requested, or the sessions couldn't be found)."""
        if self._device.lower() != "cuda" or self._model is None:
            return None
        sessions = list(_find_sessions(self._model))
        if not sessions:
            return None
        firsts = [s.get_providers()[0] for s in sessions]
        if any(p != "CUDAExecutionProvider" for p in firsts):
            logger.error("Parakeet sessions not all on GPU: %s", firsts)
            return False
        return True

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
