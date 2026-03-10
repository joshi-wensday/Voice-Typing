"""Progressive multi-pass transcription manager — incremental edition.

Architecture
------------
The session transcript is divided into two zones:

    ┌─────────────────────────────┬────────────────────────────────┐
    │  locked_text  (immutable)   │  unrefined_segs  (pending)     │
    │  already refined — NEVER    │  segments since last successful │
    │  re-processed or changed    │  refinement pass               │
    └─────────────────────────────┴────────────────────────────────┘

Each time a pause-refinement pass fires it:
  1. Transcribes ONLY the ``unrefined_segs`` audio.
  2. Appends the result to ``locked_text``.
  3. Moves those segments to ``locked_segs`` (audio retained for final pass).
  4. Clears ``unrefined_segs``.
  5. Emits the full ``locked_text`` so the UI can replace the display.

Previously refined text is therefore locked in permanently — it is never
re-processed or changed during normal operation.

Final refinement (``final_refine=True``)
-----------------------------------------
When dictation stops and the user has opted in, ``_do_final`` re-transcribes
the *entire* session (``locked_segs`` + remaining ``unrefined_segs``) in
window-sized chunks.  The ``locked_text`` is reset and rebuilt from scratch,
producing a single high-quality whole-session transcript.

Without ``final_refine``, only the remaining ``unrefined_segs`` are processed
(incremental behaviour — locked text is left unchanged).

If ``unrefined_segs`` has accumulated more than ``window_sec`` (35 s) of audio
(e.g. because several refinements were deferred), the oldest segments are
committed with their original draft text rather than re-transcribed.  This
keeps every transcription call within the model's optimal 30–40 s range.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

_MIN_AUDIO_SEC = 4.0          # skip refinement if less audio than this
_OPTIMAL_WINDOW_SEC = 35.0    # Canary-Qwen optimal transcription window


class ProgressiveTranscriber:
    """Incremental refinement: only new, unrefined segments are ever processed.

    Public interface
    ----------------
    add_segment(audio, draft_text)  – call after every VAD segment
    finalize()                      – trigger final chunked refinement
    reset()                         – clear all state (Clear button / new session)

    Callbacks
    ---------
    on_draft_text(text)             – append a new draft segment to the UI
    on_refined_text(text, final)    – replace all UI text with the locked text
    on_status(status)               – "idle" | "refining" | "finalizing"
    """

    def __init__(
        self,
        engine,
        sample_rate: int = 16000,
        pause_sec: float = 3.0,
        pause_refine: bool = False,
        final_refine: bool = False,
        window_sec: float = _OPTIMAL_WINDOW_SEC,
    ) -> None:
        self._engine = engine
        self._sample_rate = sample_rate
        self._pause_sec = pause_sec
        self._pause_refine = pause_refine
        self._final_refine = final_refine
        self._window_sec = window_sec

        self._lock = threading.Lock()

        # Immutable zone: grows only via _append_locked, never modified in place.
        self._locked_text: str = ""

        # Audio archive for already-locked segments.
        # Kept so _do_final can re-transcribe the whole session when final_refine=True.
        self._locked_segs: list[tuple[np.ndarray, str]] = []

        # Pending zone: segments accumulated since the last successful refinement.
        # Each entry: (audio_array, draft_text)
        self._unrefined_segs: list[tuple[np.ndarray, str]] = []

        self._pause_timer: Optional[threading.Timer] = None
        self._running_refinement = False

        self.on_draft_text: Optional[Callable[[str], None]] = None
        self.on_refined_text: Optional[Callable[[str, bool], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_segment(self, audio: np.ndarray, draft_text: str) -> None:
        """Record a new VAD segment and emit its draft text immediately.

        Always stores the audio even when transcription returned empty text so
        that refinement passes have access to the complete session audio.
        """
        with self._lock:
            self._unrefined_segs.append((audio.copy(), draft_text or ""))

        if self.on_draft_text and draft_text:
            self.on_draft_text(draft_text)

        if self._pause_refine:
            self._reset_pause_timer()

    def finalize(self) -> None:
        """Trigger final refinement (called on stop_dictation).

        If final_refine=True: re-transcribes the whole session for maximum
        accuracy (locked_segs + unrefined_segs in window-sized chunks).
        If final_refine=False: processes only remaining unrefined_segs.
        Always blocking — dictation is stopping so we wait for completion.
        """
        self._cancel_pause_timer()
        threading.Thread(
            target=self._run_refinement, args=(True,),
            daemon=True, name="vype-final-refine",
        ).start()

    def reset(self) -> None:
        """Clear all state.  Called by [Clear] or when a new session starts."""
        self._cancel_pause_timer()
        with self._lock:
            self._locked_text = ""
            self._locked_segs.clear()
            self._unrefined_segs.clear()
        self._emit_status("idle")

    # ------------------------------------------------------------------
    # Pause timer
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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _concat_audio(segs: list[tuple[np.ndarray, str]]) -> np.ndarray:
        if not segs:
            return np.empty(0, dtype=np.float32)
        return np.concatenate([s[0] for s in segs])

    @staticmethod
    def _join_drafts(segs: list[tuple[np.ndarray, str]]) -> str:
        parts = [s[1] for s in segs if s[1]]
        return " ".join(parts)

    def _split_window(
        self, segs: list[tuple[np.ndarray, str]]
    ) -> tuple[list, list]:
        """Return (older_segs, window_segs) where window_segs ≤ window_sec."""
        window_samples = int(self._window_sec * self._sample_rate)
        accumulated = 0
        cut = 0  # default: all in older (nothing in window)

        for i in range(len(segs) - 1, -1, -1):
            accumulated += segs[i][0].size
            if accumulated >= window_samples:
                cut = i
                break

        return segs[:cut], segs[cut:]

    def _append_locked(self, new_text: str) -> None:
        """Thread-safe append to locked_text with smart sentence joining.

        If the existing locked text ends without sentence-ending punctuation
        and the new text begins with a capital letter (suggesting a new
        sentence), inserts '. ' as the separator instead of just ' '.
        This corrects the common case where the STT model omits a terminal
        full stop between consecutive utterances.
        """
        if not new_text:
            return
        with self._lock:
            if self._locked_text:
                last_char = self._locked_text[-1]
                first_char = new_text[0]
                # Missing terminal punctuation + new sentence (capital start) → add period
                if last_char.isalpha() and first_char.isupper():
                    sep = ". "
                else:
                    sep = " " if last_char not in (" ", "\n") else ""
                self._locked_text = self._locked_text + sep + new_text
            else:
                self._locked_text = new_text

    def _get_locked(self) -> str:
        with self._lock:
            return self._locked_text

    # ------------------------------------------------------------------
    # Refinement
    # ------------------------------------------------------------------

    def _run_refinement(self, final: bool = False) -> None:
        if self._running_refinement:
            logger.debug("Refinement skipped — previous pass still running")
            return
        self._running_refinement = True
        try:
            if final:
                self._do_final()
            else:
                self._do_pause()
        except Exception as exc:
            logger.error("Refinement error: %s", exc, exc_info=True)
        finally:
            self._running_refinement = False
            self._emit_status("idle")

    # ── Pause pass ────────────────────────────────────────────────────────

    def _do_pause(self) -> None:
        """Non-blocking incremental refinement of the pending segments."""
        # Snapshot the pending list
        with self._lock:
            segs = list(self._unrefined_segs)
        n = len(segs)

        if not segs:
            return

        # If accumulated audio exceeds the optimal window, commit the oldest
        # segments as draft (lock them in without re-transcribing) and only
        # transcribe the most recent window_sec of audio.
        total_samples = sum(s[0].size for s in segs)
        if total_samples > int(self._window_sec * self._sample_rate):
            older, window_segs = self._split_window(segs)
            # Commit older segments using their draft text
            older_text = self._join_drafts(older)
            if older_text:
                self._append_locked(older_text)
            segs_to_transcribe = window_segs
        else:
            segs_to_transcribe = segs

        if not segs_to_transcribe:
            return

        audio = self._concat_audio(segs_to_transcribe)
        audio_sec = len(audio) / self._sample_rate

        if audio_sec < _MIN_AUDIO_SEC:
            logger.debug("Pause refinement skipped — only %.1f s of new audio", audio_sec)
            return

        self._emit_status("refining")
        logger.info("Pause refinement — %.1f s new audio  (locked so far: %d chars)",
                    audio_sec, len(self._get_locked()))

        # Non-blocking: defer rather than stall the live stream thread
        result = self._engine.transcribe_nowait(audio, sample_rate=self._sample_rate)
        if result is None:
            logger.debug("Pause refinement deferred — engine busy; retrying after next pause")
            self._emit_status("idle")
            if self._pause_refine:
                self._reset_pause_timer()
            return

        # ── Success: lock in the refined text ─────────────────────────────
        self._append_locked(result.text)
        new_locked = self._get_locked()

        with self._lock:
            # Archive the processed segments so _do_final can re-use their audio.
            self._locked_segs.extend(segs)  # segs == snapshot of first n unrefined_segs
            # Remove the segments we just processed; keep any that arrived
            # in the background while we were transcribing.
            self._unrefined_segs = self._unrefined_segs[n:]
            new_pending = list(self._unrefined_segs)

        logger.info("Pause refinement done — locked text now %d chars", len(new_locked))

        # Tell the UI: replace all displayed text with the locked text
        if self.on_refined_text:
            self.on_refined_text(new_locked, False)

        # Re-emit any draft segments that arrived while we were transcribing
        # so the UI shows them as pending (dimmed) after the refined portion.
        for _, draft in new_pending:
            if draft and self.on_draft_text:
                self.on_draft_text(draft)

    # ── Final pass ────────────────────────────────────────────────────────

    def _do_final(self) -> None:
        """Blocking chunked refinement on stop_dictation.

        final_refine=True  → whole-session re-transcription: combines locked_segs
                             + unrefined_segs, resets locked_text, rebuilds from
                             scratch in window-sized chunks for maximum accuracy.
        final_refine=False → incremental: processes only the remaining
                             unrefined_segs and appends to locked_text (default).
        """
        with self._lock:
            unrefined = list(self._unrefined_segs)
            n = len(unrefined)
            if self._final_refine:
                all_segs = list(self._locked_segs) + unrefined
            else:
                all_segs = unrefined

        if not all_segs:
            # Nothing to process — emit whatever is locked as final
            locked = self._get_locked()
            if locked and self.on_refined_text:
                self.on_refined_text(locked, True)
            return

        total_sec = sum(s[0].size for s in all_segs) / self._sample_rate
        self._emit_status("finalizing")
        mode = "whole-session" if self._final_refine else "incremental"
        logger.info("Final %s refinement — %.1f s in %d segments",
                    mode, total_sec, len(all_segs))

        if self._final_refine:
            # Reset locked text — we rebuild it entirely from the whole session
            with self._lock:
                self._locked_text = ""
                self._locked_segs = []

        chunk_samples = int(self._window_sec * self._sample_rate)
        chunk_segs: list = []
        chunk_size = 0

        for seg in all_segs:
            chunk_segs.append(seg)
            chunk_size += seg[0].size
            if chunk_size >= chunk_samples:
                self._transcribe_chunk_blocking(chunk_segs)
                chunk_segs = []
                chunk_size = 0

        # Tail
        if chunk_segs:
            tail_sec = chunk_size / self._sample_rate
            if tail_sec >= _MIN_AUDIO_SEC:
                self._transcribe_chunk_blocking(chunk_segs)
            else:
                # Too short for reliable transcription — keep the draft
                tail_text = self._join_drafts(chunk_segs)
                if tail_text:
                    self._append_locked(tail_text)

        new_locked = self._get_locked()

        with self._lock:
            self._unrefined_segs = self._unrefined_segs[n:]

        logger.info("Final refinement done — %d chars total", len(new_locked))
        if self.on_refined_text:
            self.on_refined_text(new_locked, True)

    def _transcribe_chunk_blocking(self, chunk_segs: list) -> None:
        """Transcribe one chunk (blocking) and append result to locked_text."""
        audio = self._concat_audio(chunk_segs)
        audio_sec = len(audio) / self._sample_rate
        logger.debug("Final chunk: %.1f s", audio_sec)
        result = self._engine.transcribe(audio, sample_rate=self._sample_rate)
        if result.text:
            self._append_locked(result.text)

    # ------------------------------------------------------------------

    def _emit_status(self, status: str) -> None:
        if self.on_status:
            try:
                self.on_status(status)
            except Exception:
                pass
