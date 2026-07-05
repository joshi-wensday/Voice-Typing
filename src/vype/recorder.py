"""Microphone capture: in-memory buffer, tail snapshots, RMS level meter.

The sounddevice stream is injectable, so unit tests feed audio by calling the
capture callback directly — no hardware needed.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np

# RMS at which the level meter saturates. Typical conversational speech at a
# desktop mic lands around 0.02-0.08 RMS; 0.08 full-scale keeps the waveform
# visibly alive instead of rendering as flat dots.
_LEVEL_FULL_SCALE_RMS = 0.08


def _sounddevice_stream_factory(samplerate: int, channels: int, device, callback):
    import sounddevice as sd

    def sd_callback(indata, frames, time_info, status):
        callback(indata[:, 0].copy())

    return sd.InputStream(
        samplerate=samplerate,
        channels=channels,
        device=device,
        dtype="float32",
        callback=sd_callback,
    )


class Recorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        device_id: int | None = None,
        stream_factory: Callable = _sounddevice_stream_factory,
    ) -> None:
        self._sample_rate = sample_rate
        self._device_id = device_id
        self._stream_factory = stream_factory
        self._stream = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._level = 0.0
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def level(self) -> float:
        """Smoothed input level in [0, 1] for the UI."""
        return self._level

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def start(self) -> None:
        if self._recording:
            return
        with self._lock:
            self._chunks = []
        self._level = 0.0
        self._stream = self._stream_factory(
            self._sample_rate, 1, self._device_id, self._on_audio
        )
        self._stream.start()
        self._recording = True

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        self._recording = False
        self._level = 0.0
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def snapshot(self, last_s: Optional[float] = None) -> np.ndarray:
        """Copy of the audio so far (optionally only the trailing window).

        Does not consume the buffer — used by the live-preview loop.
        """
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks)
        if last_s is not None:
            audio = audio[-int(last_s * self._sample_rate):]
        return audio

    def _on_audio(self, chunk: np.ndarray) -> None:
        with self._lock:
            self._chunks.append(chunk)
        rms = float(np.sqrt(np.mean(chunk**2))) if chunk.size else 0.0
        # square-root curve: perceptually livelier response at quiet levels
        target = min(1.0, (rms / _LEVEL_FULL_SCALE_RMS) ** 0.5)
        # light exponential smoothing so the pill's bars don't flicker
        self._level = 0.6 * target + 0.4 * self._level
