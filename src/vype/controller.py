"""Vype controller — Canary-only dictation pipeline.

Pipeline
--------
  AudioCapture → SileroVADSegmenter → CanaryQwenEngine → OutputHandler

Each VAD segment goes through:
  1. RMS amplitude gate        (discard near-silent frames)
  2. Canary transcription      (SALM, FP16, rolling text context)
  3. Regex command check       (zero-latency, no LLM)
  4. Type text / execute command
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .audio.capture import AudioCapture, SileroVADSegmenter
from .config.manager import ConfigManager
from .output.handler import OutputHandler
from .stt.canary_engine import CanaryQwenEngine

logger = logging.getLogger(__name__)

# Minimum RMS a VAD segment must have before calling Canary.
# 0.002 ≈ -54 dBFS — well below speech, well above digital silence.
_MIN_SEGMENT_RMS = 0.002

# Maximum typed segments remembered for SCRATCH_THAT deletion.
_MAX_TYPED_SEGMENTS = 50

# Inline key-press map for command dispatch.
_KEY_DISPATCH: dict[str, str | tuple[str, ...]] = {
    "SAVE":         "ctrl+s",
    "UNDO":         "ctrl+z",
    "DELETE_WORD":  "ctrl+backspace",
    "DELETE_LINE":  ("shift+home", "backspace"),
}


# ---------------------------------------------------------------------------
# Command patterns  (matched against the raw transcript, fullmatch semantics)
# ---------------------------------------------------------------------------

_COMMAND_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\s*(new line|newline)[.!?]?\s*",          re.I), "NEW_LINE"),
    (re.compile(r"\s*(new paragraph)[.!?]?\s*",             re.I), "NEW_PARAGRAPH"),
    (re.compile(r"\s*(stop dictation|stop listening)[.!?]?\s*", re.I), "STOP"),
    (re.compile(r"\s*(save( the| this)? file|save)[.!?]?\s*",   re.I), "SAVE"),
    (re.compile(r"\s*(undo( that)?)[.!?]?\s*",              re.I), "UNDO"),
    (re.compile(r"\s*(delete word|delete last word)[.!?]?\s*",  re.I), "DELETE_WORD"),
    (re.compile(r"\s*(delete line|delete that)[.!?]?\s*",   re.I), "DELETE_LINE"),
    (re.compile(
        r"\s*(remove|delete|scratch|scrap|erase|wipe)\s+(that\s+)?"
        r"(previous\s+|last\s+)?(sentence|paragraph)[.!?]?\s*", re.I),
        "DELETE_SENTENCE"),
    (re.compile(r"\s*(scratch|scrap|cancel|remove|erase|wipe) that\b.*[.!?]?\s*", re.I), "SCRATCH_THAT"),
    (re.compile(r"\s*(bullet point|add bullet)[.!?]?\s*",   re.I), "BULLET_POINT"),
]


def _regex_command(text: str) -> Optional[str]:
    """Return a tool name if text is an unambiguous voice command, else None."""
    for pattern, tool in _COMMAND_PATTERNS:
        if pattern.fullmatch(text.strip()):
            return tool
    return None


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

@dataclass
class DictationState:
    recording: bool = False
    processing: bool = False


class VoiceTypingController:
    def __init__(self, config: Optional[ConfigManager] = None) -> None:
        self.cfg = config or ConfigManager()
        c = self.cfg.config

        self.audio = AudioCapture(
            sample_rate=c.audio.sample_rate,
            channels=c.audio.channels,
            device_id=c.audio.device_id,
            chunk_duration=c.audio.chunk_duration,
        )

        self.vad = SileroVADSegmenter(
            sample_rate=c.audio.sample_rate,
            threshold=c.vad.threshold,
            min_speech_duration_ms=c.vad.min_speech_duration_ms,
            min_silence_duration_ms=c.vad.min_silence_duration_ms,
            max_segment_sec=c.vad.max_segment_sec,
        )

        self.stt = CanaryQwenEngine(
            model=c.stt.model,
            device=c.stt.device,
            language=c.stt.language,
            max_new_tokens=c.stt.max_new_tokens,
            enable_pnc=c.stt.enable_pnc,
            context_tail_chars=c.stt.context_tail_chars,
        )

        self.output = OutputHandler(c)

        # Typed text tracking
        self._typed_tail: str = ""          # rolling text → Canary context
        self._typed_segments: list[str] = [] # individual segments → SCRATCH_THAT

        self.state = DictationState()
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_stream = threading.Event()

        # UI callbacks
        self.on_status_change: Optional[Callable[[str], None]] = None

        # Optional integrated output (set externally before start)
        # Type: ProgressiveTranscriber | None — imported lazily to avoid circular deps
        self.progressive = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_dictation(self) -> None:
        if self.state.recording:
            return
        self._typed_tail = ""
        self._typed_segments = []
        if self.progressive is not None:
            self.progressive.reset()
        self.vad.reset()
        self._stop_stream.clear()
        self.stt.preload()
        self.audio.start_recording()
        self.state.recording = True
        self._set_status("recording")
        self._stream_thread = threading.Thread(
            target=self._stream_loop, daemon=True, name="vype-stream"
        )
        self._stream_thread.start()
        logger.info("Dictation started — model=%s device=%s", self.cfg.config.stt.model, self.cfg.config.stt.device)

    def stop_dictation(self) -> None:
        if not self.state.recording:
            return
        self.state.recording = False
        self._stop_stream.set()
        self.audio.stop_recording()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=3.0)
        self.stt.reset_context()
        if self.progressive is not None and self.cfg.config.ui.integrated_output_final_refine:
            self.progressive.finalize()
        self._set_status("idle")
        logger.info("Dictation stopped")

    def toggle(self) -> None:
        if self.state.processing:
            logger.debug("Toggle ignored — currently processing")
            return
        if not self.state.recording:
            self.start_dictation()
        else:
            self.stop_dictation()

    # ------------------------------------------------------------------
    # Stream loop
    # ------------------------------------------------------------------

    def _stream_loop(self) -> None:
        for segment in self.vad.iter_segments(
            self.audio,
            poll_interval=0.05,
            stop_event=self._stop_stream,
        ):
            if self._stop_stream.is_set():
                break
            self.state.processing = True
            self._set_status("processing")
            try:
                self._process_segment(segment)
            except Exception as exc:
                logger.error("Segment error: %s", exc, exc_info=True)
            finally:
                self.state.processing = False
                self._set_status("recording" if self.state.recording else "idle")

    def _process_segment(self, segment: np.ndarray) -> None:
        """Core pipeline: RMS gate → Canary → command check → type."""
        sr = self.cfg.config.audio.sample_rate

        # 1. Amplitude gate
        rms = float(np.sqrt(np.mean(segment ** 2)))
        if rms < _MIN_SEGMENT_RMS:
            logger.debug("RMS %.5f below threshold — skipping", rms)
            return

        # 2. Transcribe
        text = self.stt.transcribe_incremental(
            segment,
            sample_rate=sr,
            initial_prompt=self._typed_tail[-self.cfg.config.stt.context_tail_chars:] or None,
        )
        if not text:
            return

        logger.debug("STT → %r", text)

        # 3. Command check → dispatch or type
        tool = _regex_command(text)
        if tool:
            logger.debug("Command: %s", tool)
            self._dispatch_command(tool)
        else:
            self._type(text)

        # 4. Feed to progressive transcriber (audio always; draft text only for non-commands)
        if self.progressive is not None:
            draft = text if not tool else ""
            self.progressive.add_segment(segment, draft)

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _dispatch_command(self, tool: str) -> None:
        if tool in _KEY_DISPATCH:
            keys = _KEY_DISPATCH[tool]
            for k in ([keys] if isinstance(keys, str) else keys):
                self.output.press_key(k)
            # Clear context after destructive edits
            if tool in ("DELETE_LINE", "DELETE_WORD", "UNDO"):
                self._typed_tail = ""
                if tool in ("DELETE_LINE", "UNDO"):
                    self._typed_segments.clear()

        elif tool == "NEW_LINE":
            self.output.inject_text("\n")
        elif tool == "NEW_PARAGRAPH":
            self.output.inject_text("\n\n")
        elif tool == "BULLET_POINT":
            self.output.inject_text("\n• ")
        elif tool == "SCRATCH_THAT":
            self._delete_last_segment()
        elif tool == "DELETE_SENTENCE":
            self._delete_last_sentence()
        elif tool == "STOP":
            self._on_stop_command()
        else:
            logger.warning("Unknown command tool: %s", tool)

    # ------------------------------------------------------------------
    # Text output
    # ------------------------------------------------------------------

    def _type(self, text: str) -> None:
        if not text:
            return
        self.output.inject_text(text)
        self._typed_tail += text
        if len(self._typed_tail) > self.cfg.config.stt.context_tail_chars * 3:
            self._typed_tail = self._typed_tail[-self.cfg.config.stt.context_tail_chars:]
        self._typed_segments.append(text)
        if len(self._typed_segments) > _MAX_TYPED_SEGMENTS:
            self._typed_segments.pop(0)

    def _rebuild_tail_from_segments(self) -> None:
        joined = "".join(self._typed_segments)
        cap = self.cfg.config.stt.context_tail_chars * 3
        self._typed_tail = joined[-cap:] if len(joined) > cap else joined

    # ------------------------------------------------------------------
    # Deletion helpers
    # ------------------------------------------------------------------

    def _delete_last_segment(self) -> bool:
        """SCRATCH_THAT: backspace over the last typed segment."""
        if not self._typed_segments:
            return False
        last = self._typed_segments.pop()
        for _ in range(len(last)):
            self.output.press_key("backspace")
        self._rebuild_tail_from_segments()
        logger.debug("SCRATCH_THAT: deleted %d chars", len(last))
        return True

    def _delete_last_sentence(self) -> bool:
        """DELETE_SENTENCE: backspace to the previous sentence boundary."""
        if not self._typed_segments:
            return False
        total = 0
        consumed = 0
        while self._typed_segments:
            seg = self._typed_segments.pop()
            total += len(seg)
            consumed += 1
            if seg.rstrip() and seg.rstrip()[-1] in ".!?":
                break
            if consumed >= 10:  # safety cap
                break
        for _ in range(total):
            self.output.press_key("backspace")
        self._rebuild_tail_from_segments()
        logger.debug("DELETE_SENTENCE: deleted %d chars across %d segment(s)", total, consumed)
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_stop_command(self) -> None:
        logger.info("STOP command — ending dictation")
        threading.Thread(target=self.stop_dictation, daemon=True).start()

    def _set_status(self, status: str) -> None:
        if self.on_status_change:
            self.on_status_change(status)
