"""Main controller coordinating audio capture, STT, command processing, and output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import re
import threading
import time

import numpy as np

from .audio.capture import AudioCapture
from .commands.definitions import PunctuationCommand
from .commands.processor import CommandProcessor
from .config.manager import ConfigManager
from .output.handler import OutputHandler
from .stt.whisper_engine import FasterWhisperEngine


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
        self.stt = FasterWhisperEngine(
            model=c.stt.model,
            device=c.stt.device,
            compute_type=c.stt.compute_type,
            language=c.stt.language,
        )
        self.processor = CommandProcessor(c)
        self.output = OutputHandler(c)
        self.state = DictationState(recording=False, processing=False)

        # Streaming segmentation
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_stream = threading.Event()
        self._accumulated_text = ""
        self._last_injected_segments: list[str] = []

        # Status callbacks (set by UI)
        self.on_status_change: Optional[Callable[[str], None]] = None  # "idle" | "recording" | "processing"

        # Segmentation parameters from config
        self._energy_threshold = c.streaming.energy_threshold
        self._min_segment_sec = c.streaming.min_segment_sec
        self._min_silence_sec = c.streaming.min_silence_sec

    def _set_status(self, status: str) -> None:
        if self.on_status_change:
            self.on_status_change(status)

    def start_dictation(self) -> None:
        if self.state.recording:
            return
        self._accumulated_text = ""
        self._last_injected_segments.clear()
        self._stop_stream.clear()
        self.stt.preload()
        self.audio.start_recording()
        self.state.recording = True
        self._set_status("recording")
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()

    def _context_tail(self, length: int = 120) -> str:
        tail = self._accumulated_text[-length:]
        return tail.strip()

    def _smooth_punctuation(self, text: str) -> str:
        # Collapse repeated punctuation
        text = re.sub(r"([\.!?,])\1+", r"\1", text)
        # Fix space before punctuation
        text = re.sub(r"\s+([\.!?,])", r"\1", text)
        # Normalize spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _inject_final(self, cleaned: str) -> None:
        cleaned = self._smooth_punctuation(cleaned)
        # Compute delta relative to accumulated text
        if cleaned.startswith(self._accumulated_text):
            delta = cleaned[len(self._accumulated_text):]
        else:
            delta = cleaned
            self._accumulated_text = ""
        # Repetition guard: avoid injecting same delta consecutively
        if delta and (not self._last_injected_segments or self._last_injected_segments[-1] != delta):
            self.output.inject_text(delta)
            self._accumulated_text += delta
            self._last_injected_segments.append(delta)
            if len(self._last_injected_segments) > 3:
                self._last_injected_segments.pop(0)

    def _finalize_segment(self, segment_buf: list[np.ndarray], sample_rate: int) -> None:
        if not segment_buf:
            return
        segment = np.concatenate(segment_buf).astype(np.float32)
        if segment.size < int(self._min_segment_sec * sample_rate):
            return
        text = self.stt.transcribe_incremental(segment, sample_rate=sample_rate, initial_prompt=self._context_tail())
        if not text:
            return
        cleaned, commands = self.processor.process(text)
        if cleaned:
            self._inject_final(cleaned)
        for cmd in commands:
            if isinstance(cmd, PunctuationCommand):
                continue
            self.output.execute_command(cmd)

    def _stream_loop(self) -> None:
        sr = self.cfg.config.audio.sample_rate
        segment_buf: list[np.ndarray] = []
        seg_len_sec = 0.0
        silence_sec = 0.0
        while not self._stop_stream.is_set():
            chunk = self.audio.drain_buffer()
            if chunk.size > 0:
                segment_buf.append(chunk)
                dur = chunk.size / float(sr)
                seg_len_sec += dur
                energy = float(np.mean(np.abs(chunk)))
                if energy < self._energy_threshold:
                    silence_sec += dur
                else:
                    silence_sec = 0.0
                if seg_len_sec >= self._min_segment_sec and silence_sec >= self._min_silence_sec:
                    self.state.processing = True
                    self._set_status("processing")
                    self._finalize_segment(segment_buf, sr)
                    segment_buf = []
                    seg_len_sec = 0.0
                    silence_sec = 0.0
                    self.state.processing = False
                    self._set_status("recording")
            else:
                time.sleep(0.05)
        self.state.processing = True
        self._set_status("processing")
        self._finalize_segment(segment_buf, sr)
        self.state.processing = False
        self._set_status("idle")

    def stop_dictation(self) -> None:
        if not self.state.recording:
            return
        self.state.recording = False
        self._stop_stream.set()
        self.audio.stop_recording()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=2.0)

    def toggle(self) -> None:
        """Toggle dictation on/off.
        
        Prevents toggling while in processing state to avoid race conditions.
        """
        # Prevent toggle while processing to avoid state conflicts
        if self.state.processing:
            print("[Controller] Toggle ignored - currently processing")
            return
        
        print(f"[Controller] Toggle called - recording={self.state.recording}, processing={self.state.processing}")
        
        if not self.state.recording:
            self.start_dictation()
        else:
            self.stop_dictation()
