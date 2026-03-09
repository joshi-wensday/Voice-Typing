"""Main controller — V2.1 First Principles pipeline.

Pipeline:
    AudioCapture -> SileroVAD -> FasterWhisper large-v3 CUDA
        -> regex command check (instant)
        -> learned command store check (instant, user-trained patterns)
        -> [optional] LLM command classifier (only for short ambiguous utterances)
        -> type text as-is  /  execute command

Key principle: Whisper output is NEVER rewritten by the LLM.
The LLM is only used to decide whether a short utterance is a command or dictation.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .audio.capture import AudioCapture, SileroVADSegmenter
from .brain.intent_router import IntentRouter, is_likely_command
from .brain.ollama_client import OllamaClient
from .config.manager import ConfigManager
from .output.handler import OutputHandler
from .skills.command_executor import CommandExecutor
from .skills.learned_commands import LearnedCommandStore
from .stt.canary_engine import CanaryQwenEngine
from .stt.whisper_engine import FasterWhisperEngine

logger = logging.getLogger(__name__)

# Maximum characters of previously typed text to pass as Whisper initial_prompt.
_CONTEXT_TAIL_CHARS = 150

# Minimum RMS amplitude a VAD segment must have before we bother calling Whisper.
# Near-silent segments (RMS < this) are a primary trigger for counting / recitation
# hallucinations — Whisper fills the silence with training data patterns.
# 0.002 ≈ -54 dBFS, well below normal speech (~-20 dBFS) but above true silence.
_MIN_SEGMENT_RMS = 0.002

# Maximum typed segments to remember for SCRATCH_THAT deletion.
_MAX_TYPED_SEGMENTS = 50

# Spoken phrases that resolve to tool names (used for voice feedback correction).
_SPOKEN_TOOL_MAP: dict[str, str] = {
    "new line": "NEW_LINE",
    "newline": "NEW_LINE",
    "new paragraph": "NEW_PARAGRAPH",
    "save": "SAVE",
    "save file": "SAVE",
    "undo": "UNDO",
    "undo that": "UNDO",
    "delete word": "DELETE_WORD",
    "delete last word": "DELETE_WORD",
    "delete line": "DELETE_LINE",
    "delete that": "DELETE_LINE",
    "scratch that": "SCRATCH_THAT",
    "cancel that": "SCRATCH_THAT",
    "remove that": "SCRATCH_THAT",
    "delete sentence": "DELETE_SENTENCE",
    "delete last sentence": "DELETE_SENTENCE",
    "delete the last sentence": "DELETE_SENTENCE",
    "delete previous sentence": "DELETE_SENTENCE",
    "remove sentence": "DELETE_SENTENCE",
    "remove last sentence": "DELETE_SENTENCE",
    "remove the last sentence": "DELETE_SENTENCE",
    "remove previous sentence": "DELETE_SENTENCE",
    "erase sentence": "DELETE_SENTENCE",
    "erase last sentence": "DELETE_SENTENCE",
    "scratch sentence": "DELETE_SENTENCE",
    "delete paragraph": "DELETE_SENTENCE",
    "remove paragraph": "DELETE_SENTENCE",
    "bullet point": "BULLET_POINT",
    "add bullet": "BULLET_POINT",
    "stop": "STOP",
    "stop listening": "STOP",
    "stop dictation": "STOP",
    "capitalize": "CAPITALIZE",
    "lowercase": "LOWERCASE",
}


def _resolve_tool_name(text: str) -> Optional[str]:
    """Map a spoken correction phrase to a tool name, or None if unrecognised."""
    key = text.lower().strip().rstrip(".!?").strip()
    return _SPOKEN_TOOL_MAP.get(key)


@dataclass
class DictationState:
    recording: bool = False
    processing: bool = False


class VoiceTypingController:
    def __init__(self, config: Optional[ConfigManager] = None) -> None:
        self.cfg = config or ConfigManager()
        c = self.cfg.config

        # --- Audio layer ---
        self.audio = AudioCapture(
            sample_rate=c.audio.sample_rate,
            channels=c.audio.channels,
            device_id=c.audio.device_id,
            chunk_duration=c.audio.chunk_duration,
        )

        # --- Silero VAD segmenter ---
        self.vad = SileroVADSegmenter(
            sample_rate=c.audio.sample_rate,
            threshold=c.vad.threshold,
            min_speech_duration_ms=c.vad.min_speech_duration_ms,
            min_silence_duration_ms=c.vad.min_silence_duration_ms,
            max_segment_sec=c.vad.max_segment_sec,
        )

        # --- STT engine ---
        backend = getattr(c.stt, "backend", "whisper")
        # Use .value for robust comparison — str(StrEnum) changed behaviour in Python 3.11
        backend_val = backend.value if hasattr(backend, "value") else str(backend)
        model_val = c.stt.model.value if hasattr(c.stt.model, "value") else str(c.stt.model)
        if backend_val == "nemo" or model_val == "canary-qwen-2.5b":
            self.stt = CanaryQwenEngine(
                model="nvidia/canary-qwen-2.5b",
                device=str(c.stt.device.value if hasattr(c.stt.device, "value") else c.stt.device),
                language=c.stt.language,
            )
        else:
            self.stt = FasterWhisperEngine(
                model=c.stt.model,
                device=c.stt.device,
                compute_type=c.stt.compute_type,
                language=c.stt.language,
            )

        # --- Output handler ---
        self.output = OutputHandler(c)

        # --- Brain layer (Ollama — command classification only) ---
        self._ollama = OllamaClient(
            endpoint=c.brain.endpoint,
            timeout=c.brain.timeout_sec,
        )
        self._brain_enabled = c.brain.enabled and c.brain.intent_routing_enabled

        self._intent_router = IntentRouter(
            client=self._ollama,
            model=c.brain.model,
        )

        self._command_executor = CommandExecutor(
            inject_text=self.output.inject_text,
            press_key=self.output.press_key,
            stop_callback=self._on_stop_command,
            scratch_that_callback=self._delete_last_segment,
            delete_sentence_callback=self._delete_last_sentence,
        )

        # --- Learned command store ---
        self.learned_store = LearnedCommandStore()

        # --- Typed text buffers ---
        # _typed_tail: rolling char buffer → Whisper initial_prompt (no LLM)
        self._typed_tail: str = ""
        # _typed_segments: individual injected segments → enables SCRATCH_THAT
        self._typed_segments: list[str] = []

        # --- Feedback state ---
        self._feedback_mode: bool = False
        self._last_command_phrase: str = ""
        self._last_command_tool: str = ""

        # --- External callbacks (wired in __main__.py) ---
        # Called after any command fires: (phrase, tool) → None
        self.on_command_fired: Optional[Callable[[str, str], None]] = None
        # Called when voice ENTER_FEEDBACK fires (to surface the correction UI)
        self.on_feedback_enter: Optional[Callable[[], None]] = None

        self.state = DictationState(recording=False, processing=False)

        self._stream_thread: Optional[threading.Thread] = None
        self._stop_stream = threading.Event()

        self.on_status_change: Optional[Callable[[str], None]] = None

        if self._brain_enabled:
            t = threading.Thread(
                target=self._ollama.warmup,
                args=(c.brain.model,),
                daemon=True,
                name="ollama-warmup",
            )
            t.start()
        else:
            logger.info("Brain layer disabled — using regex + learned commands only")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_dictation(self) -> None:
        if self.state.recording:
            return
        self._typed_tail = ""
        self._typed_segments = []
        self._feedback_mode = False
        self.vad.reset()
        self._stop_stream.clear()
        self.stt.preload()
        self.audio.start_recording()
        self.state.recording = True
        self._set_status("recording")
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
        logger.info("Dictation started (model=%s device=%s)", self.cfg.config.stt.model, self.cfg.config.stt.device)

    def stop_dictation(self) -> None:
        if not self.state.recording:
            return
        self.state.recording = False
        self._stop_stream.set()
        self.audio.stop_recording()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=3.0)
        self._feedback_mode = False
        # Always reset the UI to idle.  The stream-loop's finally block does
        # the same when it exits mid-segment, but if dictation is stopped while
        # the VAD is simply waiting for speech (no active segment), the loop
        # exits silently without ever updating the status, leaving the overlay
        # frozen on "recording".
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

    def apply_correction(self, phrase: str, tool: str) -> None:
        """Apply a UI-sourced command correction and persist it.

        Called from the main thread via the overlay correction dialog.
        """
        self.learned_store.add(phrase, tool)
        logger.info("Correction applied (UI): %r -> %s", phrase, tool)

    # ------------------------------------------------------------------
    # Stream loop
    # ------------------------------------------------------------------

    def _stream_loop(self) -> None:
        for speech_segment in self.vad.iter_segments(
            self.audio,
            poll_interval=0.05,
            stop_event=self._stop_stream,
        ):
            if not self.state.recording and self._stop_stream.is_set():
                break
            self.state.processing = True
            self._set_status("processing")
            try:
                self._process_segment(speech_segment)
            except Exception as exc:
                logger.error("Error processing segment: %s", exc, exc_info=True)
            finally:
                self.state.processing = False
                self._set_status("recording" if self.state.recording else "idle")

    def _process_segment(self, segment: np.ndarray) -> None:
        """V2.1 pipeline: VAD segment -> Whisper -> commands -> type."""
        sr = self.cfg.config.audio.sample_rate

        # --- Amplitude gate: discard near-silent segments ---
        # With vad_filter=False in transcribe_incremental, Whisper no longer runs
        # its own silence detector on the incoming audio.  A Silero VAD false-positive
        # (e.g. a keyboard click, breath noise) can result in a very quiet segment
        # reaching Whisper, which then hallucinates counting sequences or recitations
        # from its training data instead of returning an empty string.
        rms = float(np.sqrt(np.mean(np.square(segment))))
        if rms < _MIN_SEGMENT_RMS:
            logger.debug("Segment RMS %.5f below threshold %.5f — skipping (likely silence)", rms, _MIN_SEGMENT_RMS)
            return

        # --- Step 1: Transcribe ---
        initial_prompt = self._typed_tail[-_CONTEXT_TAIL_CHARS:] or None
        text = self.stt.transcribe_incremental(segment, sample_rate=sr, initial_prompt=initial_prompt)

        if not text:
            return

        text = _clean_whisper_output(text)
        if not text:
            return

        # --- Echo guard: Whisper sometimes copies back its own initial_prompt ---
        # When a segment's cleaned text already appears verbatim inside the
        # prompt we just sent, it means Whisper is hallucinating the context
        # rather than transcribing new speech.  Discard the segment and clear
        # the tail so the next call starts with a fresh prompt.
        if initial_prompt and text.strip() in initial_prompt:
            logger.warning(
                "Echo guard: Whisper echoed initial_prompt — discarding and "
                "clearing tail. Segment: %r", text,
            )
            self._typed_tail = ""
            return

        logger.debug("STT: %r", text)

        # --- Feedback mode: next utterance is a correction ---
        if self._feedback_mode:
            self._handle_voice_correction(text)
            return

        # --- Step 2: Explicit regex commands (zero latency) ---
        command_tool = _regex_command(text)
        if command_tool:
            logger.debug("Regex command: %s", command_tool)
            self._dispatch_command(text, command_tool)
            return

        # --- Step 3: Learned command patterns (zero latency, user-trained) ---
        learned_tool = self.learned_store.match(text)
        if learned_tool:
            logger.debug("Learned command: %s (phrase=%r)", learned_tool, text)
            self._dispatch_command(text, learned_tool)
            return

        # --- Step 4: LLM command gate (only for short ambiguous utterances) ---
        if self._brain_enabled and is_likely_command(text):
            result = self._intent_router.classify_command(text)
            if result.is_command and result.tool:
                logger.debug("LLM command: %s", result.tool)
                self._dispatch_command(text, result.tool)
                return

        # --- Step 5: Type as-is ---
        self._type(text)

    def _dispatch_command(self, phrase: str, tool: str) -> None:
        """Execute a command, handle meta-commands, and notify listeners."""
        if tool == "ENTER_FEEDBACK":
            self._feedback_mode = True
            self._set_status("feedback")
            logger.info("Feedback mode activated — waiting for correction phrase")
            if self.on_feedback_enter:
                self.on_feedback_enter()
            return

        if tool == "CANCEL_FEEDBACK":
            self._feedback_mode = False
            self._set_status("recording" if self.state.recording else "idle")
            logger.info("Feedback mode cancelled")
            return

        self._command_executor.execute(tool)

        # Keyboard-driven commands change the document in ways we can't track
        # in _typed_segments.  Clear the context tail so Whisper doesn't use
        # stale (now-deleted) text as initial_prompt and hallucinate repetitions.
        # For UNDO and DELETE_LINE we also clear segments because we don't know
        # how much text was actually removed from the document.
        if tool in ("DELETE_LINE", "UNDO"):
            self._typed_tail = ""
            self._typed_segments.clear()
        elif tool == "DELETE_WORD":
            self._typed_tail = ""

        # Track for feedback
        self._last_command_phrase = phrase
        self._last_command_tool = tool

        if self.on_command_fired:
            self.on_command_fired(phrase, tool)

    def _handle_voice_correction(self, text: str) -> None:
        """Handle the correction utterance spoken while in feedback mode.

        Resolution order:
        1. Fast exact-phrase lookup via _resolve_tool_name (e.g. "delete line")
        2. LLM classification fallback for natural-language phrases
           (e.g. "I wanted you to delete the previous line")
        """
        tool = _resolve_tool_name(text)

        if tool is None and self._brain_enabled:
            # Natural-language correction — ask the LLM to classify the intent.
            result = self._intent_router.classify_command(text)
            if result.is_command and result.tool:
                tool = result.tool
                logger.debug("Voice correction resolved via LLM: %r -> %s", text, tool)

        if tool is None:
            # Last-resort keyword scan: pull intent from any recognisable noun
            # in the correction phrase (e.g. "you were meant to remove the whole
            # sentence" → DELETE_SENTENCE, "delete the previous line" → DELETE_LINE).
            lower = text.lower()
            if any(w in lower for w in ("sentence", "paragraph")):
                tool = "DELETE_SENTENCE"
            elif "line" in lower:
                tool = "DELETE_LINE"
            elif "word" in lower:
                tool = "DELETE_WORD"
            if tool:
                logger.debug("Voice correction resolved via keywords: %r -> %s", text, tool)

        if tool:
            logger.info("Voice correction: %r -> %s (was: %r -> %s)",
                        self._last_command_phrase, tool,
                        self._last_command_phrase, self._last_command_tool)
            self.learned_store.add(self._last_command_phrase, tool)
            # Execute immediately so the correction takes effect right now,
            # not just for future invocations.
            self._command_executor.execute(tool)
            if self.on_command_fired:
                self.on_command_fired(self._last_command_phrase, tool)
        else:
            logger.warning(
                "Voice correction: could not resolve %r as a tool — "
                "try a simpler phrase like 'delete sentence' or 'scratch that'",
                text,
            )

        self._feedback_mode = False
        self._set_status("recording" if self.state.recording else "idle")

    def _type(self, text: str) -> None:
        """Type text, update the context tail, and record the segment for SCRATCH_THAT."""
        if text:
            self.output.inject_text(text)
            self._typed_tail += text
            if len(self._typed_tail) > _CONTEXT_TAIL_CHARS * 3:
                self._typed_tail = self._typed_tail[-_CONTEXT_TAIL_CHARS:]
            self._typed_segments.append(text)
            if len(self._typed_segments) > _MAX_TYPED_SEGMENTS:
                self._typed_segments.pop(0)

    def _rebuild_tail_from_segments(self) -> None:
        """Rebuild _typed_tail from the current _typed_segments after a deletion.

        More reliable than the fragile endswith-trim approach: always produces a
        tail that exactly reflects the segments still remaining in the buffer.
        """
        joined = "".join(self._typed_segments)
        self._typed_tail = joined[-_CONTEXT_TAIL_CHARS * 3:] if len(joined) > _CONTEXT_TAIL_CHARS * 3 else joined

    def _delete_last_segment(self) -> bool:
        """Delete the last typed segment by sending exact backspace keystrokes.

        This is the SCRATCH_THAT implementation. Backspacing by character count
        works across all applications (Notepad, Word, VS Code, browsers, etc.)
        without relying on Ctrl+Z which only undoes one inject_text call.
        """
        if not self._typed_segments:
            logger.debug("SCRATCH_THAT: no typed segments to delete")
            return False
        last = self._typed_segments.pop()
        char_count = len(last)
        logger.debug("SCRATCH_THAT: deleting %d chars (%r)", char_count, last)
        for _ in range(char_count):
            self.output.press_key("backspace")
        self._rebuild_tail_from_segments()
        return True

    def _delete_last_sentence(self) -> bool:
        """Delete all typed segments back to and including the previous sentence boundary.

        Walks backwards through _typed_segments, popping and accumulating char
        counts, until it consumes a segment whose last non-whitespace character
        is a sentence-ending punctuation mark (. ! ?).  This handles the common
        case where a single spoken sentence is split into multiple VAD chunks by
        natural mid-sentence pauses.

        Safety cap: stops after consuming at most 10 segments so a single command
        cannot wipe out large amounts of text unintentionally.
        """
        if not self._typed_segments:
            logger.debug("DELETE_SENTENCE: no typed segments to delete")
            return False

        total_chars = 0
        consumed: list[str] = []

        while self._typed_segments:
            seg = self._typed_segments.pop()
            consumed.append(seg)
            total_chars += len(seg)

            # Stop once we've consumed a segment that closes a sentence
            stripped = seg.rstrip()
            if stripped and stripped[-1] in ".!?":
                break

            # Safety cap — don't walk back further than 10 segments
            if len(consumed) >= 10:
                break

        logger.debug(
            "DELETE_SENTENCE: deleting %d chars across %d segment(s)",
            total_chars, len(consumed),
        )
        for _ in range(total_chars):
            self.output.press_key("backspace")

        self._rebuild_tail_from_segments()
        return True

    def _on_stop_command(self) -> None:
        logger.info("STOP command received — ending dictation")
        self.stop_dictation()

    def _set_status(self, status: str) -> None:
        if self.on_status_change:
            self.on_status_change(status)


# ---------------------------------------------------------------------------
# Module-level helpers (no state, easily testable)
# ---------------------------------------------------------------------------

# Number words Whisper uses when it hallucinates a counting sequence.
# When 5+ consecutive tokens in a segment are all number words or bare digits,
# the segment is discarded as a counting hallucination.
_NUMBER_WORDS: frozenset[str] = frozenset({
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand",
})
_DIGIT_RE = re.compile(r"^\d+$")
_COUNTING_HALLUCINATION_RUN = 5  # consecutive number tokens needed to trigger discard


def _is_number_token(token: str) -> bool:
    """Return True if `token` is a number word or a bare integer digit string."""
    t = token.strip(",.!?").lower()
    return t in _NUMBER_WORDS or bool(_DIGIT_RE.match(t))


_COMMAND_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*(new line|newline)[.!?]?\s*$", re.I), "NEW_LINE"),
    (re.compile(r"^\s*(new paragraph)[.!?]?\s*$", re.I), "NEW_PARAGRAPH"),
    (re.compile(r"^\s*(stop dictation|stop listening)[.!?]?\s*$", re.I), "STOP"),
    (re.compile(r"^\s*(save( the| this)? file|save)[.!?]?\s*$", re.I), "SAVE"),
    (re.compile(r"^\s*(undo( that)?)[.!?]?\s*$", re.I), "UNDO"),
    # DELETE: exact phrase or with trailing context ("delete that last line", "delete the last sentence")
    (re.compile(r"^\s*(delete( that| last word| last line| the last\b.*)?)[.!?]?\s*$", re.I), "DELETE_LINE"),
    # DELETE_SENTENCE: explicitly targets a whole sentence or paragraph
    (re.compile(
        r"^\s*(remove|delete|scratch|scrap|erase|wipe)\s+(that\s+)?(previous\s+|last\s+)?(sentence|paragraph)[.!?]?\s*$",
        re.I), "DELETE_SENTENCE"),
    # SCRATCH_THAT: allow synonyms (scrap/scratch/cancel/remove/erase/wipe) and
    # optional trailing context words ("scrap that last sentence", "scratch that paragraph")
    (re.compile(r"^\s*(scratch|scrap|cancel|remove|erase|wipe) that\b.*[.!?]?\s*$", re.I), "SCRATCH_THAT"),
    (re.compile(r"^\s*(bullet point|add bullet)[.!?]?\s*$", re.I), "BULLET_POINT"),
    # Feedback meta-commands
    (re.compile(r"^\s*(that was wrong|wrong command|incorrect)[.!?]?\s*$", re.I), "ENTER_FEEDBACK"),
    (re.compile(r"^\s*(cancel feedback|stop feedback)[.!?]?\s*$", re.I), "CANCEL_FEEDBACK"),
]


def _regex_command(text: str) -> Optional[str]:
    """Return a tool name if the text is an unambiguous explicit command, else None."""
    for pattern, tool in _COMMAND_PATTERNS:
        if pattern.match(text):
            return tool
    return None


def _clean_whisper_output(text: str) -> str:
    """Minimal post-processing of Whisper output — spacing and punctuation only.

    Applies two hallucination guards:
    1. Repetition guard — discards segments where a single word dominates (>40%).
    2. Counting guard — discards segments containing 5+ consecutive number
       words or digits, the signature of a Whisper counting hallucination
       (triggered by silence or a prior context that ended with numbers).
    """
    text = re.sub(r"([.!?,])\1+", r"\1", text)
    text = re.sub(r"\s+([.!?,])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    words = text.lower().split()

    # Guard 1 — repeated single word (e.g. "the the the the")
    if len(words) >= 4:
        top_word, top_count = Counter(words).most_common(1)[0]
        if top_count / len(words) > 0.4:
            logger.warning(
                "Hallucination guard (repetition): discarding segment "
                "(word=%r, %d/%d occurrences): %r",
                top_word, top_count, len(words), text,
            )
            return ""

    # Guard 2 — counting sequence (e.g. "one, two, three, four, five...")
    # Whisper hallucinates this when audio is near-silent or when the prior
    # context ended with numeric content and condition_on_previous_text was on.
    if len(words) >= _COUNTING_HALLUCINATION_RUN:
        max_run = current_run = 0
        for token in words:
            if _is_number_token(token):
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0
        if max_run >= _COUNTING_HALLUCINATION_RUN:
            logger.warning(
                "Hallucination guard (counting): discarding sequential-number "
                "segment (run=%d): %r",
                max_run, text,
            )
            return ""

    return text
