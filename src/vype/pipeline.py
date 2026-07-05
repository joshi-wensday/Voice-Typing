"""The orchestrator: hotkey events → record → transcribe → (clean) → paste.

One utterance is one linear pass on a worker thread. The live-preview loop
re-transcribes the accumulated audio from scratch each tick; preview text is
disposable and never feeds the paste path.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .cleanup import CleanupUnavailable
from .config import Config
from .fsm import Command, DictationFSM, State

logger = logging.getLogger(__name__)

# Snapshots shorter than this aren't worth a preview pass.
_MIN_PREVIEW_S = 0.5


class Pipeline:
    def __init__(
        self,
        recorder,
        transcriber,
        cleaner,
        injector,
        history,
        config: Config,
        run_async: bool = True,
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._cleaner = cleaner
        self._injector = injector
        self._history = history
        self._cfg = config
        self._run_async = run_async

        self._fsm = DictationFSM(tap_threshold_ms=config.hotkey.tap_threshold_ms)
        self._fsm_lock = threading.Lock()
        # Serializes engine access: the final pass blocks on it, preview ticks skip.
        self._engine_lock = threading.Lock()
        self._preview_stop = threading.Event()
        self._preview_thread: Optional[threading.Thread] = None

        self.cleanup_enabled: bool = config.cleanup.enabled

        # UI callbacks (all may be invoked from worker threads)
        self.on_state: Callable[[str], None] = lambda s: None
        self.on_preview: Callable[[str], None] = lambda t: None
        self.on_error: Callable[[str], None] = lambda m: None

    @property
    def state(self) -> State:
        return self._fsm.state

    @property
    def recorder(self):
        return self._recorder

    @property
    def history(self):
        return self._history

    # ── Hotkey entry points (called from the keyboard hook thread) ──────────

    def press(self, now: float | None = None) -> None:
        self._handle(lambda t: self._fsm.on_press(t_ms=t * 1000), now)

    def release(self, now: float | None = None) -> None:
        self._handle(lambda t: self._fsm.on_release(t_ms=t * 1000), now)

    def escape(self, now: float | None = None) -> None:
        self._handle(lambda t: self._fsm.on_escape(), now)

    def _handle(self, transition, now: float | None) -> None:
        t = time.monotonic() if now is None else now
        with self._fsm_lock:
            command = transition(t)
        self._execute(command)

    # ── Command execution ────────────────────────────────────────────────────

    def _execute(self, command: Command) -> None:
        if command is Command.START_RECORDING:
            self._recorder.start()
            self.on_state("recording")
            self._start_preview_loop()
        elif command is Command.STOP_AND_PROCESS:
            self._stop_preview_loop()
            audio = self._recorder.stop()
            self.on_state("processing")
            if self._run_async:
                threading.Thread(
                    target=self._process, args=(audio,), daemon=True, name="vype-process"
                ).start()
            else:
                self._process(audio)
        elif command is Command.CANCEL:
            self._stop_preview_loop()
            self._recorder.stop()
            self.on_state("idle")

    def _process(self, audio) -> None:
        try:
            duration_s = len(audio) / self._recorder_sample_rate()
            if duration_s < self._cfg.min_utterance_s:
                logger.debug("Discarding %.2f s utterance (below minimum)", duration_s)
                return

            with self._engine_lock:
                raw = self._transcriber.transcribe(audio)
            if not raw:
                return

            text, cleaned = raw, None
            if self.cleanup_enabled and self._cleaner is not None:
                try:
                    text = cleaned = self._cleaner.clean(raw)
                except CleanupUnavailable as exc:
                    logger.warning("Cleanup unavailable (%s) — pasting raw", exc)
                    self.on_error("Cleanup offline — pasted raw transcript")
                    text, cleaned = raw, None

            self._injector.paste(text)
            self._history.append(raw=raw, cleaned=cleaned)
        except Exception as exc:
            logger.error("Pipeline error: %s", exc, exc_info=True)
            self.on_error(str(exc))
        finally:
            with self._fsm_lock:
                self._fsm.on_processing_done()
            self.on_state("idle")

    # ── Live preview ─────────────────────────────────────────────────────────

    def preview_tick(self) -> None:
        """One preview pass: snapshot → transcribe → emit. Skips if engine busy."""
        if self._fsm.state not in (State.HELD_RECORDING, State.HANDSFREE_RECORDING):
            return
        snapshot = self._recorder.snapshot(last_s=self._cfg.ui.preview_window_s)
        if len(snapshot) < _MIN_PREVIEW_S * self._recorder_sample_rate():
            return
        if not self._engine_lock.acquire(blocking=False):
            return  # final pass or previous tick still running — skip, never queue
        try:
            text = self._transcriber.transcribe(snapshot)
        except Exception as exc:
            logger.debug("Preview tick failed: %s", exc)
            return
        finally:
            self._engine_lock.release()
        if text:
            self.on_preview(text)

    def _start_preview_loop(self) -> None:
        if not (self._run_async and self._cfg.ui.live_preview):
            return
        self._preview_stop.clear()
        self._preview_thread = threading.Thread(
            target=self._preview_loop, daemon=True, name="vype-preview"
        )
        self._preview_thread.start()

    def _stop_preview_loop(self) -> None:
        self._preview_stop.set()

    def _preview_loop(self) -> None:
        while not self._preview_stop.wait(timeout=self._cfg.ui.preview_interval_s):
            try:
                self.preview_tick()
            except Exception as exc:
                logger.debug("Preview loop error: %s", exc)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _recorder_sample_rate(self) -> int:
        return getattr(self._recorder, "sample_rate", self._cfg.audio.sample_rate)
