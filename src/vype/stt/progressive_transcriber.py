"""Progressive multi-pass transcription manager.

Maintains a rolling audio buffer of all speech since dictation started.
As the user keeps talking, longer audio chunks are periodically re-transcribed
to produce progressively more accurate output — more audio context means fewer
word errors at segment boundaries.

Refinement tiers
----------------
1. Draft   — immediately after each VAD segment (called from controller thread).
2. Pause   — fires N seconds after the last segment (user paused speaking);
             re-transcribes the whole session buffer.
3. Final   — triggered on stop_dictation(); one last whole-session pass to
             produce the definitive transcript.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Minimum accumulated speech before running a refinement pass.
# Avoids wasting a full inference cycle on a single short word.
_MIN_AUDIO_SEC = 5.0


class ProgressiveTranscriber:
    """Accumulates audio segments and runs background refinement passes.

    Public interface
    ----------------
    add_segment(audio, draft_text)   – call after each VAD segment is transcribed
    finalize()                       – trigger final whole-session refinement
    reset()                          – clear everything (called on Clear / new session)

    Callbacks (set before use)
    --------------------------
    on_draft_text(text)  – new draft segment text to append to the UI
    on_refined_text(text, final)  – full refined transcript; replace UI content
    on_status(status)    – "idle" | "refining" | "finalizing"
    """

    def __init__(
        self,
        engine,  # CanaryQwenEngine — imported lazily to avoid circular deps
        sample_rate: int = 16000,
        pause_sec: float = 3.0,
    ) -> None:
        self._engine = engine
        self._sample_rate = sample_rate
        self._pause_sec = pause_sec

        self._lock = threading.Lock()
        self._audio_buf: list[np.ndarray] = []   # one entry per VAD segment

        self._pause_timer: Optional[threading.Timer] = None
        self._running_refinement = False          # guard: no concurrent refinements

        # Callbacks — wired externally
        self.on_draft_text: Optional[Callable[[str], None]] = None
        self.on_refined_text: Optional[Callable[[str, bool], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_segment(self, audio: np.ndarray, draft_text: str) -> None:
        """Record a new VAD segment and emit its draft text.

        Called from the controller's stream thread for every successfully
        transcribed segment.  The audio is stored for later refinement.
        """
        with self._lock:
            self._audio_buf.append(audio.copy())

        # Emit draft text immediately
        if self.on_draft_text and draft_text:
            self.on_draft_text(draft_text)

        # Reset the pause timer — refinement fires N seconds after last speech
        self._reset_pause_timer()

    def finalize(self) -> None:
        """Trigger the final whole-session refinement (call on stop_dictation).

        Cancels any pending pause timer and runs a final pass in a thread.
        """
        self._cancel_pause_timer()
        threading.Thread(
            target=self._run_refinement, args=(True,),
            daemon=True, name="vype-final-refine",
        ).start()

    def reset(self) -> None:
        """Clear audio buffer and cancel all pending timers.

        Called when the user presses [Clear] or starts a new session.
        """
        self._cancel_pause_timer()
        with self._lock:
            self._audio_buf.clear()
        self._emit_status("idle")

    # ------------------------------------------------------------------
    # Internal — pause timer
    # ------------------------------------------------------------------

    def _reset_pause_timer(self) -> None:
        self._cancel_pause_timer()
        self._pause_timer = threading.Timer(
            self._pause_sec,
            lambda: threading.Thread(
                target=self._run_refinement, args=(False,),
                daemon=True, name="vype-pause-refine",
            ).start(),
        )
        self._pause_timer.daemon = True
        self._pause_timer.start()

    def _cancel_pause_timer(self) -> None:
        if self._pause_timer is not None:
            self._pause_timer.cancel()
            self._pause_timer = None

    # ------------------------------------------------------------------
    # Internal — refinement passes
    # ------------------------------------------------------------------

    def _get_full_audio(self) -> np.ndarray:
        with self._lock:
            if not self._audio_buf:
                return np.empty(0, dtype=np.float32)
            return np.concatenate(self._audio_buf)

    def _run_refinement(self, final: bool = False) -> None:
        """Re-transcribe the entire audio buffer and emit refined text.

        ``final`` is True only for the stop-dictation pass.
        """
        # Don't stack concurrent refinements
        if self._running_refinement:
            logger.debug("Skipping refinement — previous pass still running")
            return
        self._running_refinement = True

        audio = self._get_full_audio()
        audio_sec = len(audio) / self._sample_rate

        if audio_sec < _MIN_AUDIO_SEC:
            logger.debug("Skipping refinement — only %.1f s of audio", audio_sec)
            self._running_refinement = False
            return

        status = "finalizing" if final else "refining"
        self._emit_status(status)
        logger.info(
            "Refinement pass (%s) — %.1f s audio", "final" if final else "pause", audio_sec
        )

        try:
            result = self._engine.transcribe(audio, sample_rate=self._sample_rate)
            text = result.text
            logger.info("Refinement complete — %d chars", len(text))
            if self.on_refined_text:
                self.on_refined_text(text, final)
        except Exception as exc:
            logger.error("Refinement failed: %s", exc, exc_info=True)
        finally:
            self._running_refinement = False
            self._emit_status("idle")

    def _emit_status(self, status: str) -> None:
        if self.on_status:
            try:
                self.on_status(status)
            except Exception:
                pass
