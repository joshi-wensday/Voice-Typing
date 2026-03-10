"""NVIDIA Canary-Qwen STT engine (SALM / NeMo SpeechLM2).

Model card : https://huggingface.co/nvidia/canary-qwen-2.5b
NeMo docs  : https://docs.nvidia.com/nemo-framework/user-guide/latest/

Pipeline per segment
--------------------
  1. Amplitude clip + RMS normalisation  → clean WAV
  2. SALM chat prompt with PnC instruction + rolling text context
  3. torch.inference_mode() + FP16 inference
  4. Basic Inverse Text Normalisation (regex, no extra deps)
  5. Returns transcript string / TranscriptionResult
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import threading
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inverse Text Normalisation rules  (applied in order, case-insensitive)
# ---------------------------------------------------------------------------
_ITN_RULES: list[tuple[re.Pattern[str], str]] = [
    # Currency
    (re.compile(r"\b(\d+(?:\.\d+)?)\s+dollars?\b", re.I),      r"$\1"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s+cents?\b",   re.I),      r"¢\1"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s+euros?\b",   re.I),      r"€\1"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s+pounds?\b",  re.I),      r"£\1"),
    # Percentage
    (re.compile(r"\b(\d+(?:\.\d+)?)\s+percent\b",  re.I),      r"\1%"),
    # Ordinal dates  e.g. "july fourth" → "July 4th"
    (re.compile(r"\bjuly\s+fourth\b",  re.I),   "July 4th"),
    (re.compile(r"\bjuly\s+4th\b",     re.I),   "July 4th"),
    # Fractions
    (re.compile(r"\b(\d+)\s+and\s+a\s+half\b", re.I),  r"\1.5"),
    # Common abbreviations spoken aloud
    (re.compile(r"\bmister\b",  re.I),  "Mr."),
    (re.compile(r"\bmissus\b",  re.I),  "Mrs."),
    (re.compile(r"\bdoctor\b",  re.I),  "Dr."),
    (re.compile(r"\bversus\b",  re.I),  "vs."),
]


def _apply_itn(text: str) -> str:
    """Apply basic Inverse Text Normalisation (no extra dependencies)."""
    for pattern, replacement in _ITN_RULES:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Model name helpers
# ---------------------------------------------------------------------------

_SHORT_MODEL_NAMES: dict[str, str] = {
    "canary-qwen-2.5b": "nvidia/canary-qwen-2.5b",
    "canary-1b":        "nvidia/canary-1b",
    "canary-1b-flash":  "nvidia/canary-1b-flash",
    "canary-1b-v2":     "nvidia/canary-1b-v2",
}


def _normalise_model_name(name: str) -> str:
    """Accept short names (e.g. 'canary-qwen-2.5b') and return the full HF ID.

    Old config.yaml files may contain the short form.  This allows the engine
    to work without requiring the user to manually edit their config.
    """
    return _SHORT_MODEL_NAMES.get(name.strip().lower(), name)


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _normalise_audio(audio: np.ndarray) -> np.ndarray:
    """Clip to [-1, 1] and RMS-normalise to -20 dBFS target.

    Canary is sensitive to amplitude; very quiet audio (<-40 dBFS) leads to
    degraded transcription quality.  Target -20 dBFS matches typical speech
    capture levels.
    """
    audio = np.clip(audio.astype(np.float32), -1.0, 1.0)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms > 1e-6:
        target_rms = 0.1          # -20 dBFS ≈ 0.1 linear
        gain = target_rms / rms
        gain = min(gain, 10.0)    # never boost by more than +20 dB
        audio = np.clip(audio * gain, -1.0, 1.0)
    return audio


def _write_temp_wav(audio: np.ndarray, sample_rate: int) -> str:
    """Write normalised float32 audio to a temp PCM-16 WAV. Returns path."""
    audio = _normalise_audio(audio)
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)

    fd, path = tempfile.mkstemp(prefix="vype_canary_", suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # int16
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    return path


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CanaryQwenEngine:
    """Wrapper around NeMo SALM ``nvidia/canary-qwen-2.5b``.

    Public interface: ``preload``, ``transcribe``, ``transcribe_incremental``,
    ``reset_context`` (clears rolling text tail on session end).
    """

    def __init__(
        self,
        model: str = "nvidia/canary-qwen-2.5b",
        device: str = "cuda",
        language: str | None = "en",
        max_new_tokens: int = 256,
        enable_pnc: bool = True,
        context_tail_chars: int = 400,
    ) -> None:
        self.model_name = _normalise_model_name(model)
        self.device = device
        self.language = str(language) if language else "en"
        self.max_new_tokens = max_new_tokens
        self.enable_pnc = enable_pnc
        self.context_tail_chars = context_tail_chars

        self._model = None
        # Shared lock so ProgressiveTranscriber's background refinement thread
        # never runs concurrently with a foreground segment transcription.
        self.inference_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_imports(self) -> None:
        try:
            import torch  # noqa: F401
            from nemo.collections.speechlm2.models import SALM  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "CanaryQwenEngine requires NVIDIA NeMo SpeechLM2.\n"
                "Install with:  pip install \"nemo_toolkit[asr]\"\n"
                "Ensure a compatible PyTorch+CUDA build is installed first."
            ) from exc

    def preload(self) -> None:
        """Load (and optionally download) the model. No-op if already loaded."""
        if self._model is not None:
            return
        self._ensure_imports()

        import torch
        from nemo.collections.speechlm2.models import SALM  # type: ignore[import]

        logger.info("Loading Canary model: %s (device=%s)", self.model_name, self.device)
        self._model = SALM.from_pretrained(self.model_name)

        dtype = torch.float16 if self.device.lower() == "cuda" else torch.float32
        try:
            self._model = self._model.to(self.device, dtype=dtype)
        except Exception:
            logger.warning("Could not move model to %s — using default placement", self.device)

        self._model.eval()
        logger.info("Canary model loaded")

    def load_model(self, model_name: str) -> None:
        """Hot-swap model at runtime."""
        self.model_name = _normalise_model_name(model_name)
        self._model = None
        self.preload()

    def reset_context(self) -> None:
        """No-op: kept for API compatibility (context tail removed)."""

    def get_supported_models(self) -> list[str]:
        return [
            "nvidia/canary-qwen-2.5b",
            "nvidia/canary-1b",
            "nvidia/canary-1b-flash",
            "nvidia/canary-1b-v2",
        ]

    # ------------------------------------------------------------------
    # Prompt engineering
    # ------------------------------------------------------------------

    def _build_prompt(self, context_tail: str = "") -> str:
        """Build the SALM chat prompt for clean speech transcription.

        Context is intentionally NOT included in the prompt.  Injecting prior
        transcript text caused the model to reproduce old text verbatim before
        generating the new transcription, producing duplication artefacts and
        occasionally echoing the instruction text itself.  Canary transcribes
        accurately from audio alone without needing rolling context in the
        prompt.
        """
        tag = getattr(self._model, "audio_locator_tag", "<|audioplaceholder|>")
        pnc = (
            "Use correct punctuation and capitalisation. "
            if self.enable_pnc else ""
        )
        return (
            f"{pnc}Transcribe the speech in the audio exactly as spoken. "
            f"Output only the transcript with no labels or commentary.\n{tag}"
        )

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _run_transcribe(self, wav_path: str, audio_sec: float) -> str:
        """Run SALM generation on a single WAV file (caller must hold inference_lock)."""
        assert self._model is not None
        import torch

        # Scale max_new_tokens to audio length: ~25 tokens/sec, min 128
        tokens = max(128, min(self.max_new_tokens, int(audio_sec * 25) + 32))

        prompt = self._build_prompt()

        with torch.inference_mode():
            answer_ids = self._model.generate(
                prompts=[
                    [
                        {
                            "role": "user",
                            "content": prompt,
                            "audio": [wav_path],
                        }
                    ]
                ],
                max_new_tokens=tokens,
            )

        text: str = self._model.tokenizer.ids_to_text(
            answer_ids[0].cpu()
        ).strip()
        return text

    def _transcribe_wav(self, wav_path: str, audio_sec: float) -> str:
        """Transcribe a WAV file and apply ITN.  Acquires inference_lock."""
        with self.inference_lock:
            try:
                raw = self._run_transcribe(wav_path, audio_sec)
            finally:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

        if not raw:
            return ""

        return _apply_itn(raw)

    # ------------------------------------------------------------------
    # Public transcription API
    # ------------------------------------------------------------------

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe a complete audio buffer. Returns TranscriptionResult."""
        if audio_data.ndim != 1:
            raise ValueError("audio_data must be a 1-D mono float32 array")
        if sample_rate != 16000:
            raise ValueError(
                f"Canary requires 16 kHz audio; got {sample_rate} Hz. "
                "Set audio.sample_rate = 16000 in config."
            )
        if self._model is None:
            self.preload()

        audio_sec = len(audio_data) / sample_rate
        wav_path = _write_temp_wav(audio_data, sample_rate)
        text = self._transcribe_wav(wav_path, audio_sec)
        return TranscriptionResult(text=text, language=self.language)

    def transcribe_incremental(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        initial_prompt: str | None = None,  # kept for API compatibility, unused
    ) -> str:
        """Transcribe a streaming audio segment. Returns plain text.

        ``initial_prompt`` is accepted for API compatibility but is no longer
        injected into the prompt (context injection caused the model to
        reproduce prior text verbatim).
        """
        if audio_data.size == 0:
            return ""
        if sample_rate != 16000:
            raise ValueError(
                f"Canary requires 16 kHz audio; got {sample_rate} Hz. "
                "Set audio.sample_rate = 16000 in config."
            )
        if self._model is None:
            self.preload()

        audio_sec = len(audio_data) / sample_rate
        wav_path = _write_temp_wav(audio_data, sample_rate)
        return self._transcribe_wav(wav_path, audio_sec)
