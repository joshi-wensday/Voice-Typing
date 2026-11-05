"""The orchestrator: hotkey events → record → transcribe → (clean) → paste.

One utterance is one linear pass on a worker thread. The live-preview loop
re-transcribes the accumulated audio from scratch each tick; preview text is
disposable and never feeds the paste path.

Never-lose guarantees: the final pass splits long recordings at pauses (no
engine input limit can swallow them), and — when an AudioSpool is attached —
the mic audio is on disk from the first chunk until its transcript has been
pasted and saved. Anything left over is picked up by recover_pending().
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .chunking import transcribe_long
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
        spool=None,
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._cleaner = cleaner
        self._injector = injector
        self._history = history
        self._cfg = config
        self._run_async = run_async
        self._spool = spool
        self._spool_rec = None  # the in-flight SpoolRecording, if any
        self._recover_lock = threading.Lock()

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
        self.on_notice: Callable[[str], None] = lambda m: None

    @property
    def state(self) -> State:
        return self._fsm.state

    @property
    def recorder(self):
        return self._recorder

    def apply_settings(self) -> None:
        """Re-read live-tunable values from the (mutated) config object."""
        self.cleanup_enabled = self._cfg.cleanup.enabled
        self._fsm.set_tap_threshold(self._cfg.hotkey.tap_threshold_ms)

    def replace_cleaner(self, cleaner) -> None:
        self._cleaner = cleaner

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
            before = self._fsm.state
            command = transition(t)
            after = self._fsm.state
        self._execute(command)
        if before is State.HELD_RECORDING and after is State.HANDSFREE_RECORDING:
            self.on_state("recording-locked")

    # ── Command execution ────────────────────────────────────────────────────

    def _execute(self, command: Command) -> None:
        if command is Command.START_RECORDING:
            self._open_spool()
            self._recorder.start()
            self.on_state("recording")
            self._start_preview_loop()
        elif command is Command.STOP_AND_PROCESS:
            self._stop_preview_loop()
            audio = self._recorder.stop()
            rec = self._close_spool()
            self.on_state("processing")
            if self._run_async:
                threading.Thread(
                    target=self._process, args=(audio, rec), daemon=True, name="vype-process"
                ).start()
            else:
                self._process(audio, rec)
        elif command is Command.CANCEL:
            self._stop_preview_loop()
            self._recorder.stop()
            rec = self._close_spool()
            if rec is not None:
                self._spool.discard(rec.path)  # cancelled on purpose
            self.on_state("idle")

    def _process(self, audio, rec=None) -> None:
        keep_audio = False
        try:
            duration_s = len(audio) / self._recorder_sample_rate()
            if duration_s < self._cfg.min_utterance_s:
                logger.debug("Discarding %.2f s utterance (below minimum)", duration_s)
                return

            with self._engine_lock:
                result = self._transcribe(audio)
            raw = result.text
            if not raw:
                return

            text, cleaned = self._clean(raw)
            if self._cfg.append_space and not text.endswith((" ", "\n", "\t")):
                self._injector.paste(text + " ")
            else:
                self._injector.paste(text)
            self._history.append(raw=raw, cleaned=cleaned)

            if not result.complete:
                keep_audio = True
                self.on_error(
                    f"{result.failed} of {result.pieces} parts couldn't be transcribed "
                    f"(marked […]).{self._saved_hint(rec)}"
                )
        except Exception as exc:
            keep_audio = True
            logger.error("Pipeline error: %s", exc, exc_info=True)
            self.on_error(f"{exc}{self._saved_hint(rec)}")
        finally:
            if rec is not None and not keep_audio:
                self._spool.discard(rec.path)
            elif rec is not None:
                logger.info("Kept recording for retry: %s", rec.path)
            with self._fsm_lock:
                self._fsm.on_processing_done()
            self.on_state("idle")

    def _transcribe(self, audio):
        """Caller holds the engine lock."""
        return transcribe_long(
            self._transcriber, audio, self._recorder_sample_rate(), self._cfg.stt.max_chunk_s
        )

    def _clean(self, raw: str) -> tuple[str, str | None]:
        if not (self.cleanup_enabled and self._cleaner is not None):
            return raw, None
        try:
            cleaned = self._cleaner.clean(raw)
            return cleaned, cleaned
        except CleanupUnavailable as exc:
            logger.warning("Cleanup unavailable (%s) — using raw", exc)
            self.on_error("Cleanup offline — used raw transcript")
            return raw, None

    # ── Audio spool (never lose a recording) ─────────────────────────────────

    @staticmethod
    def _saved_hint(rec) -> str:
        if rec is None:
            return ""
        return " Your audio is saved — tray → Retry unfinished recordings."

    def _open_spool(self) -> None:
        self._spool_rec = self._spool.begin() if self._spool is not None else None
        self._recorder.tap = self._spool_rec.write if self._spool_rec is not None else None

    def _close_spool(self):
        self._recorder.tap = None
        rec, self._spool_rec = self._spool_rec, None
        if rec is not None:
            rec.close()
            self._spool.release(rec)
        return rec

    def recover_pending(self, announce_empty: bool = False) -> None:
        """Transcribe recordings left on disk (failed or interrupted) into history.

        Never pastes — whatever has focus now isn't where you were dictating.
        A recording is deleted only once it transcribed completely.
        """
        if self._spool is None:
            return
        if not self._recover_lock.acquire(blocking=False):
            return  # already running
        try:
            pending = self._spool.pending()
            if not pending:
                if announce_empty:
                    self.on_notice("No unfinished recordings.")
                return
            recovered = still_failed = 0
            sr = self._recorder_sample_rate()
            for path in pending:
                audio = self._spool.load(path)
                if len(audio) < self._cfg.min_utterance_s * sr:
                    self._spool.discard(path)
                    continue
                try:
                    with self._engine_lock:
                        result = self._transcribe(audio)
                except Exception as exc:
                    logger.error("Recovery of %s failed: %s", path, exc)
                    still_failed += 1
                    continue
                if result.text:
                    _, cleaned = self._clean(result.text)
                    self._history.append(raw=result.text, cleaned=cleaned)
                if result.complete:
                    self._spool.discard(path)
                    recovered += 1
                else:
                    still_failed += 1  # partial text saved, audio kept for another go
            if recovered:
                plural = "s" if recovered != 1 else ""
                self.on_notice(
                    f"Recovered {recovered} unfinished recording{plural} — "
                    "click the pill to copy from history."
                )
            if still_failed:
                plural = "s" if still_failed != 1 else ""
                self.on_error(
                    f"{still_failed} recording{plural} still couldn't be fully transcribed "
                    "— kept on disk for another retry."
                )
        finally:
            self._recover_lock.release()

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
