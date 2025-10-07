"""Main controller coordinating audio capture, STT, command processing, and output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import threading
import time

import numpy as np

from .audio.capture import AudioCapture
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

        # Streaming
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_stream = threading.Event()
        self._accumulated_text = ""

        # Status callbacks (set by UI)
        self.on_status_change: Optional[Callable[[str], None]] = None  # "idle" | "recording" | "processing"

    def _set_status(self, status: str) -> None:
        if self.on_status_change:
            self.on_status_change(status)

    def start_dictation(self) -> None:
        if self.state.recording:
            return
        self._accumulated_text = ""
        self._stop_stream.clear()
        self.stt.preload()
        self.audio.start_recording()
        self.state.recording = True
        self._set_status("recording")
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()

    def _stream_loop(self) -> None:
        # Drain audio periodically, transcribe, inject delta
        sr = self.cfg.config.audio.sample_rate
        while not self._stop_stream.is_set():
            chunk = self.audio.drain_buffer()
            if chunk.size > 0:
                text = self.stt.transcribe_incremental(chunk, sample_rate=sr)
                if text:
                    cleaned, commands = self.processor.process(text)
                    if cleaned:
                        # Compute delta vs accumulated
                        if cleaned.startswith(self._accumulated_text):
                            delta = cleaned[len(self._accumulated_text):]
                        else:
                            # Fallback: inject full cleaned and reset accumulator
                            delta = cleaned
                            self._accumulated_text = ""
                        if delta:
                            self.output.inject_text(delta)
                            self._accumulated_text += delta
                    for cmd in commands:
                        self.output.execute_command(cmd)
            time.sleep(0.1)
        # After stop requested, flush remaining buffer and mark processing till done
        self.state.processing = True
        self._set_status("processing")
        tail = self.audio.drain_buffer()
        if tail.size > 0:
            text = self.stt.transcribe_incremental(tail, sample_rate=sr)
            if text:
                cleaned, commands = self.processor.process(text)
                if cleaned:
                    if cleaned.startswith(self._accumulated_text):
                        delta = cleaned[len(self._accumulated_text):]
                    else:
                        delta = cleaned
                        self._accumulated_text = ""
                    if delta:
                        self.output.inject_text(delta)
                        self._accumulated_text += delta
                for cmd in commands:
                    self.output.execute_command(cmd)
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
        if not self.state.recording:
            self.start_dictation()
        else:
            self.stop_dictation()
