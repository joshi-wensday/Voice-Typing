"""NVIDIA NeMo Canary-Qwen STT engine.

Model card: https://huggingface.co/nvidia/canary-qwen-2.5b

This engine is an optional backend. It requires NeMo (and torch) to be installed.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import tempfile
import wave
from typing import Optional

import numpy as np

from ..config.manager import ConfigManager
from .text_processor import TextProcessor


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = None


def _float32_to_pcm16(audio: np.ndarray) -> bytes:
    """Convert mono float32 [-1, 1] audio to PCM16 bytes."""
    if audio.ndim != 1:
        raise ValueError("audio_data must be 1-D mono float32 array")
    a = np.nan_to_num(audio.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype(np.int16)
    return pcm.tobytes()


def _write_temp_wav(audio: np.ndarray, sample_rate: int) -> str:
    """Write a temporary mono PCM16 WAV and return its path."""
    pcm_bytes = _float32_to_pcm16(audio)
    f = tempfile.NamedTemporaryFile(prefix="vype_canary_", suffix=".wav", delete=False)
    f.close()
    with wave.open(f.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm_bytes)
    return f.name


class CanaryQwenEngine:
    """Wrapper around NeMo SALM `nvidia/canary-qwen-2.5b`."""

    def __init__(
        self,
        model: str = "nvidia/canary-qwen-2.5b",
        device: str = "cuda",
        language: str | None = "en",
        max_new_tokens: int = 128,
    ) -> None:
        self.model_name = model
        self.device = device
        self.language = str(language) if language is not None else None
        self.max_new_tokens = int(max_new_tokens)

        self._model = None
        self._cfgm = ConfigManager()

        # Keep the lightweight local filler pass as a fallback (Refiner may be disabled).
        self._text_processor = TextProcessor(
            remove_fillers=self._cfgm.config.stt.remove_filler_words,
            improve_grammar=False,
        )

    def _ensure_imports(self) -> None:
        try:
            import torch  # noqa: F401
            from nemo.collections.speechlm2.models import SALM  # noqa: F401
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Canary-Qwen engine requires NVIDIA NeMo. Install with:\n\n"
                '  pip install "vype[canary]"\n\n'
                "Also install a compatible torch build first (CUDA or CPU)."
            ) from e

    def preload(self) -> None:
        if self._model is not None:
            return
        self._ensure_imports()
        from nemo.collections.speechlm2.models import SALM

        self._model = SALM.from_pretrained(self.model_name)

        # Best-effort device move. NeMo wraps torch modules; `.to()` is usually present.
        try:  # pragma: no cover
            if self.device and str(self.device).lower() in ("cuda", "cpu"):
                self._model = self._model.to(str(self.device).lower())
        except Exception:
            # If device placement fails, let NeMo/Torch decide defaults.
            pass

    def load_model(self, model_name: str) -> None:
        # Allow switching between NeMo checkpoints; re-init on next preload.
        self.model_name = model_name
        self._model = None

    def get_supported_models(self) -> list[str]:
        # Keep API parity with FasterWhisperEngine (used by some UI helpers).
        return ["canary-qwen-2.5b"]

    def _build_prompt(self, initial_prompt: str | None) -> str:
        # In ASR mode, Canary-Qwen uses a chat prompt + an audio locator tag.
        # We include rolling context as a hint, but keep it short to avoid
        # steering the transcript away from the audio.
        tag = getattr(self._model, "audio_locator_tag", "<|audioplaceholder|>")
        ctx = (initial_prompt or "").strip()
        if ctx:
            ctx = ctx[-240:]
            return (
                "Transcribe the following audio with correct punctuation and capitalization.\n"
                f"Prior typed context (may help with names/terms): {ctx}\n"
                f"{tag}"
            )
        return f"Transcribe the following audio with correct punctuation and capitalization: {tag}"

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        if self._model is None:
            self.preload()
        assert self._model is not None

        if int(sample_rate) != 16000:
            raise ValueError("Canary-Qwen expects 16000 Hz mono audio. Set audio.sample_rate to 16000.")

        wav_path = _write_temp_wav(audio_data, sample_rate=sample_rate)
        try:
            prompt_text = self._build_prompt(initial_prompt=None)

            answer_ids = self._model.generate(
                prompts=[
                    [
                        {
                            "role": "user",
                            "content": prompt_text,
                            "audio": [wav_path],
                        }
                    ]
                ],
                max_new_tokens=self.max_new_tokens,
            )

            text = self._model.tokenizer.ids_to_text(answer_ids[0].cpu()).strip()
            text = self._text_processor.process(text)
            return TranscriptionResult(text=text, language=self.language)
        finally:
            try:
                os.unlink(wav_path)
            except Exception:
                pass

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

        if int(sample_rate) != 16000:
            raise ValueError("Canary-Qwen expects 16000 Hz mono audio. Set audio.sample_rate to 16000.")

        wav_path = _write_temp_wav(audio_data, sample_rate=sample_rate)
        try:
            prompt_text = self._build_prompt(initial_prompt=initial_prompt)

            answer_ids = self._model.generate(
                prompts=[
                    [
                        {
                            "role": "user",
                            "content": prompt_text,
                            "audio": [wav_path],
                        }
                    ]
                ],
                max_new_tokens=self.max_new_tokens,
            )
            text = self._model.tokenizer.ids_to_text(answer_ids[0].cpu()).strip()
            text = self._text_processor.process(text)
            return text
        finally:
            try:
                os.unlink(wav_path)
            except Exception:
                pass

