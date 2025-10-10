"""Audio capture utilities using sounddevice.

Provides device enumeration and start/stop recording with a streaming buffer.
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np
import sounddevice as sd


class AudioCapture:
    """Audio capture with device selection and level metering.

    Captures mono audio at a configured sample rate and channels using a
    background callback that appends chunks to an in-memory buffer.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device_id: int | None = None,
        chunk_duration: float = 0.5,
    ) -> None:
        """Initialize the audio capture instance.

        Args:
            sample_rate: Target sample rate in Hz (e.g., 16000)
            channels: Number of input channels (1 for mono)
            device_id: Optional device index from sounddevice
            chunk_duration: Duration of each audio callback chunk in seconds
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_id = device_id
        self.chunk_frames = int(self.sample_rate * chunk_duration)

        self._buffer: list[np.ndarray] = []
        self._buffer_lock = threading.Lock()
        self._level: float = 0.0
        
        # For real-time visualization
        self._latest_chunk: np.ndarray = np.zeros(0, dtype=np.float32)
        self._chunk_lock = threading.Lock()

        self._stream: sd.InputStream | None = None
        self._is_recording = False

    @property
    def is_recording(self) -> bool:
        """Whether recording is active."""
        return self._is_recording

    def list_devices(self) -> list[dict[str, Any]]:
        """List available input devices.

        Returns:
            List of device dictionaries with keys: id, name, default_samplerate,
            max_input_channels
        """
        devices = sd.query_devices()
        result: list[dict[str, Any]] = []
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                result.append(
                    {
                        "id": idx,
                        "name": dev.get("name"),
                        "default_samplerate": dev.get("default_samplerate"),
                        "max_input_channels": dev.get("max_input_channels"),
                    }
                )
        return result

    def set_device(self, device_id: int) -> None:
        """Select the input device by index.

        Args:
            device_id: Device index as returned by list_devices
        """
        self.device_id = device_id

    def _on_audio(self, indata: np.ndarray) -> None:
        """Handle incoming audio chunk.

        Args:
            indata: Chunk of shape (frames, channels) float32 in [-1, 1]
        """
        # Convert to mono if needed
        if indata.ndim == 2 and indata.shape[1] > 1:
            mono = indata.mean(axis=1)
        else:
            mono = indata.reshape(-1)

        # Update simple RMS level [0, 1]
        rms = float(np.sqrt(np.mean(np.square(mono))) if mono.size else 0.0)
        self._level = max(0.0, min(1.0, rms))

        with self._buffer_lock:
            self._buffer.append(mono.copy())
        
        # Store latest chunk for visualization
        with self._chunk_lock:
            self._latest_chunk = mono.copy()

    def _sd_callback(self, indata: np.ndarray, frames: int, time: Any, status: sd.CallbackFlags) -> None:
        if status:
            # Status can be logged if needed; ignored here for simplicity
            pass
        self._on_audio(indata)

    def start_recording(self) -> None:
        """Begin audio capture into an internal buffer."""
        if self._is_recording:
            return
        with self._buffer_lock:
            self._buffer.clear()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._sd_callback,
            blocksize=self.chunk_frames,
            device=self.device_id,
        )
        self._stream.start()
        self._is_recording = True

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return concatenated mono float32 audio.

        Returns:
            1-D numpy array of float32 samples in range [-1, 1]
        """
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._is_recording = False

        with self._buffer_lock:
            if not self._buffer:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._buffer).astype(np.float32)
            self._buffer.clear()
            return audio

    def drain_buffer(self) -> np.ndarray:
        """Return and clear any buffered audio without stopping.

        Useful for streaming transcription to fetch incremental samples.
        """
        with self._buffer_lock:
            if not self._buffer:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._buffer).astype(np.float32)
            self._buffer.clear()
            return audio

    def get_level(self) -> float:
        """Get recent RMS audio level in [0.0, 1.0]."""
        return self._level
    
    def get_latest_chunk(self) -> np.ndarray:
        """Get the latest audio chunk for visualization.
        
        Returns:
            1-D numpy array of float32 samples in range [-1, 1]
        """
        with self._chunk_lock:
            return self._latest_chunk.copy() if self._latest_chunk.size > 0 else np.zeros(0, dtype=np.float32)
