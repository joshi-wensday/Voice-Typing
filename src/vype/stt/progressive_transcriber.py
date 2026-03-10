"""Progressive multi-pass transcription manager — sliding window edition.

Architecture overview
---------------------
The model (Canary-Qwen-2.5B) has an optimal transcription window of 30–40
seconds.  Feeding the full session (which can be minutes long) hurts accuracy
and causes token-limit truncation that silently drops text.

Instead we use a **sliding window** approach inspired by convolutional networks:

    ┌────────────────────────────┬──────────────────────────────────┐
    │  committed  (older segs)   │  active window  (last ~35 s)     │
    │  draft quality — locked in │  re-transcribed on each refine   │
    └────────────────────────────┴──────────────────────────────────┘

When a refinement pass runs it:
  1. Takes only the last ``window_sec`` (default 35 s) of audio.
  2. Re-transcribes that window with Canary → more accurate for that slice.
  3. Emits: committed_text + refined_window_text.

The committed portion uses the original per-segment draft text (already very
accurate for Canary) — it never gets re-transcribed and never gets lost.
As the session grows, segments older than the window graduate to committed.

Refinement tiers
----------------
1. Draft  — immediate, per VAD-segment.  Typed live, shown dimmed.
2. Pause  — fires ``pause_sec`` after last segment; re-transcribes window.
             Only active when ``pause_refine=True``.  Non-blocking (defers
             if engine is busy with a live segment).
3. Final  — triggered on stop_dictation().  Processes in 35-second chunks,
             concatenates results.  Only runs when the controller calls
             ``finalize()`` (controlled by ``integrated_output_final_refine``
             config flag, default False).
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Minimum accumulated audio before we bother running a refinement pass.
_MIN_AUDIO_SEC = 4.0

# Canary-Qwen-2.5B optimal transcription window (seconds).
# Accuracy peaks at 30–40 s; beyond that the model was not trained on and
# tends to degrade, potentially truncating or dropping words.
_OPTIMAL_WINDOW_SEC = 35.0


class ProgressiveTranscriber:
    """Accumulates audio segments and runs background sliding-window refinement.

    Public interface
    ----------------
    add_segment(audio, draft_text)   – called after each VAD segment
    finalize()                       – trigger final chunked refinement
    reset()                          – clear everything (Clear button / new session)

    Callbacks (wire before first use)
    ----------------------------------
    on_draft_text(text)              – append draft text to the UI
    on_refined_text(text, final)     – replace all UI text with refined version
    on_status(status)                – "idle" | "refining" | "finalizing"
    """

    def __init__(
        self,
        engine,
        sample_rate: int = 16000,
        pause_sec: float = 3.0,
        pause_refine: bool = False,
        window_sec: float = _OPTIMAL_WINDOW_SEC,
    ) -> None:
        self._engine = engine
        self._sample_rate = sample_rate
        self._pause_sec = pause_sec
        self._pause_refine = pause_refine
        self._window_sec = window_sec

        self._lock = threading.Lock()
        # Each entry: (audio_array, draft_text).  Grows one entry per VAD segment.
        self._segments: list[tuple[np.ndarray, str]] = []

        self._pause_timer: Optional[threading.Timer] = None
        self._running_refinement = False

        self.on_draft_text: Optional[Callable[[str], None]] = None
        self.on_refined_text: Optional[Callable[[str, bool], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_segment(self, audio: np.ndarray, draft_text: str) -> None:
        """Record a new VAD segment and emit its draft text.

        Always stores the audio regardless of whether transcription succeeded —
        this guarantees the full session audio is available for refinement even
        when individual segments produce empty text.
        """
        with self._lock:
            self._segments.append((audio.copy(), draft_text or ""))

        if self.on_draft_text and draft_text:
            self.on_draft_text(draft_text)

        if self._pause_refine:
            self._reset_pause_timer()

    def finalize(self) -> None:
        """Trigger final refinement in a background thread.

        Processes the session in ``window_sec``-sized chunks and concatenates
        the results, keeping each chunk within the model's optimal range.
        """
        self._cancel_pause_timer()
        threading.Thread(
            target=self._run_refinement, args=(True,),
            daemon=True, name="vype-final-refine",
        ).start()

    def reset(self) -> None:
        """Clear all state.  Called by the [Clear] button or on new session."""
        self._cancel_pause_timer()
        with self._lock:
            self._segments.clear()
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
    # Internal — segment partitioning
    # ------------------------------------------------------------------

    def _partition(self, window_sec: float) -> tuple[list, list]:
        """Split ``_segments`` into (pre_window, window) by audio duration.

        ``window`` contains the most recent ``window_sec`` seconds of segments.
        ``pre_window`` contains everything older — their draft text is used as-is.
        """
        with self._lock:
            segs = list(self._segments)  # snapshot

        if not segs:
            return [], []

        window_samples = int(window_sec * self._sample_rate)
        accumulated = 0
        cut = len(segs)  # default: all in window

        # Walk backwards to find the cut point
        for i in range(len(segs) - 1, -1, -1):
            accumulated += segs[i][0].size
            if accumulated >= window_samples:
                cut = i
                break

        return segs[:cut], segs[cut:]

    def _segments_to_audio(self, segs: list) -> np.ndarray:
        if not segs:
            return np.empty(0, dtype=np.float32)
        return np.concatenate([s[0] for s in segs])

    def _segments_to_text(self, segs: list) -> str:
        """Join the draft texts of a segment list with single spaces."""
        parts = [s[1] for s in segs if s[1]]
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Internal — refinement
    # ------------------------------------------------------------------

    def _run_refinement(self, final: bool = False) -> None:
        """Sliding-window refinement.

        Pause pass (final=False):
            Re-transcribes the last ``window_sec`` of audio; prepends committed
            draft text (segments older than the window) unchanged.
            Uses ``transcribe_nowait()`` — defers if engine is busy.

        Final pass (final=True):
            Processes ALL audio in ``window_sec`` chunks and concatenates the
            results, keeping every chunk inside the model's optimal range.
            Uses blocking ``transcribe()`` since dictation has stopped.
        """
        if self._running_refinement:
            logger.debug("Skipping refinement — previous pass still running")
            return
        self._running_refinement = True

        try:
            if final:
                self._run_final_chunked()
            else:
                self._run_pause_window()
        except Exception as exc:
            logger.error("Refinement failed: %s", exc, exc_info=True)
        finally:
            self._running_refinement = False
            self._emit_status("idle")

    def _run_pause_window(self) -> None:
        """Non-blocking pause refinement — last window_sec of audio only."""
        pre_segs, win_segs = self._partition(self._window_sec)

        win_audio = self._segments_to_audio(win_segs)
        win_sec = len(win_audio) / self._sample_rate

        if win_sec < _MIN_AUDIO_SEC:
            logger.debug("Pause refinement skipped — only %.1f s in window", win_sec)
            return

        self._emit_status("refining")
        logger.info(
            "Pause refinement — window %.1f s  |  committed segs: %d",
            win_sec, len(pre_segs),
        )

        result = self._engine.transcribe_nowait(win_audio, sample_rate=self._sample_rate)
        if result is None:
            logger.debug("Pause refinement deferred — engine busy; will retry after next pause")
            self._emit_status("idle")
            if self._pause_refine:
                self._reset_pause_timer()
            return

        committed_text = self._segments_to_text(pre_segs)
        refined_window = result.text
        full_text = (committed_text + " " + refined_window).strip() if committed_text else refined_window

        logger.info("Pause refinement done — %d committed chars + %d refined chars",
                    len(committed_text), len(refined_window))
        if self.on_refined_text:
            self.on_refined_text(full_text, False)

    def _run_final_chunked(self) -> None:
        """Blocking final refinement — processes all segments in window-sized chunks."""
        with self._lock:
            all_segs = list(self._segments)

        if not all_segs:
            logger.debug("Final refinement skipped — no segments")
            return

        total_sec = sum(s[0].size for s in all_segs) / self._sample_rate
        if total_sec == 0:
            return

        self._emit_status("finalizing")
        logger.info("Final refinement — %.1f s total audio in %d segments", total_sec, len(all_segs))

        # Slice into window-sized chunks and transcribe each
        chunk_results: list[str] = []
        chunk_samples = int(self._window_sec * self._sample_rate)

        # Group segments into chunks by cumulative sample count
        chunk_segs: list = []
        chunk_size = 0

        for seg in all_segs:
            chunk_segs.append(seg)
            chunk_size += seg[0].size
            if chunk_size >= chunk_samples:
                chunk_audio = self._segments_to_audio(chunk_segs)
                chunk_sec = len(chunk_audio) / self._sample_rate
                logger.debug("Final chunk: %.1f s", chunk_sec)
                result = self._engine.transcribe(chunk_audio, sample_rate=self._sample_rate)
                if result.text:
                    chunk_results.append(result.text)
                chunk_segs = []
                chunk_size = 0

        # Remaining segments that didn't fill a full chunk
        if chunk_segs:
            chunk_audio = self._segments_to_audio(chunk_segs)
            chunk_sec = len(chunk_audio) / self._sample_rate
            if chunk_sec >= _MIN_AUDIO_SEC:
                logger.debug("Final chunk (tail): %.1f s", chunk_sec)
                result = self._engine.transcribe(chunk_audio, sample_rate=self._sample_rate)
                if result.text:
                    chunk_results.append(result.text)
            else:
                # Too short for reliable transcription — keep the draft text
                tail_text = self._segments_to_text(chunk_segs)
                if tail_text:
                    chunk_results.append(tail_text)

        full_text = " ".join(chunk_results)
        logger.info("Final refinement done — %d chars across %d chunks",
                    len(full_text), len(chunk_results))
        if self.on_refined_text:
            self.on_refined_text(full_text, True)

    def _emit_status(self, status: str) -> None:
        if self.on_status:
            try:
                self.on_status(status)
            except Exception:
                pass
