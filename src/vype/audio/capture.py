"""Audio capture utilities using sounddevice.

Provides device enumeration and start/stop recording with a streaming buffer,
plus a Silero VAD pre-segmenter that only forwards confirmed speech frames.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Generator, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


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


class SileroVADSegmenter:
    """Pre-segments incoming audio into confirmed speech chunks using Silero VAD.

    Silero VAD is a lightweight ONNX neural network that runs in real-time and
    distinguishes speech from silence/noise far more reliably than energy thresholds.

    Usage pattern:
        segmenter = SileroVADSegmenter(sample_rate=16000)
        for speech_chunk in segmenter.iter_segments(audio_capture):
            text = whisper.transcribe(speech_chunk)

    The model is downloaded on first use via torch.hub and cached locally.
    Requires: torch or onnxruntime (see pyproject.toml [v2] extras)
    """

    # Silero VAD operates on 512 samples at 16kHz (32ms windows)
    _WINDOW_SIZE_16K = 512
    _WINDOW_SIZE_8K = 256

    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.4,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 800,
        max_segment_sec: float = 10.0,
    ) -> None:
        """Initialise the Silero VAD segmenter.

        Args:
            sample_rate: Audio sample rate (8000 or 16000)
            threshold: VAD confidence threshold [0, 1]. Higher = less sensitive.
            min_speech_duration_ms: Minimum speech duration to emit a segment.
            min_silence_duration_ms: Silence gap that triggers end-of-segment.
                800ms is the sweet spot — short enough to feel responsive, long
                enough not to cut on natural mid-sentence pauses (300-500ms).
            max_segment_sec: Force a segment after this many seconds of continuous
                speech even if silence never arrives. Prevents unbounded accumulation
                during long unbroken utterances.
        """
        if sample_rate not in (8000, 16000):
            raise ValueError("Silero VAD only supports 8000 or 16000 Hz")

        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_samples = int(min_speech_duration_ms * sample_rate / 1000)
        self.min_silence_samples = int(min_silence_duration_ms * sample_rate / 1000)
        self.max_speech_samples = int(max_segment_sec * sample_rate)
        self._window_size = self._WINDOW_SIZE_16K if sample_rate == 16000 else self._WINDOW_SIZE_8K

        self._model: Optional[Any] = None
        self._model_utils: Optional[Any] = None
        self._lock = threading.Lock()
        self._load_attempted: bool = False  # only try once; avoids per-chunk retry spam

        # Persistent cross-chunk VAD state — must survive between process_chunk calls
        self._speech_buf: list[np.ndarray] = []
        self._speech_samples: int = 0
        self._silence_samples: int = 0
        self._in_speech: bool = False

    def _load_model(self) -> None:
        """Load Silero VAD via torch.hub (downloads on first call, cached after)."""
        try:
            import torch  # type: ignore[import-untyped]
            model, utils = torch.hub.load(  # type: ignore[attr-defined]
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
            self._model = model
            self._model_utils = utils
            logger.info("Silero VAD model loaded (torch backend)")
        except Exception as exc:
            logger.warning("Failed to load Silero VAD via torch.hub: %s — falling back to energy VAD", exc)
            self._model = None

    def is_available(self) -> bool:
        """Return True if the VAD model loaded successfully.

        Only attempts to load once — subsequent calls return the cached result
        immediately without re-trying, preventing per-chunk log spam on failure.
        """
        if not self._load_attempted:
            with self._lock:
                if not self._load_attempted:
                    self._load_model()
                    self._load_attempted = True
        return self._model is not None

    def _vad_probability(self, window: np.ndarray) -> float:
        """Run the VAD model on a single window and return speech probability."""
        try:
            import torch  # type: ignore[import-untyped]
            tensor = torch.from_numpy(window).unsqueeze(0)  # type: ignore[attr-defined]
            with torch.no_grad():  # type: ignore[attr-defined]
                prob = self._model(tensor, self.sample_rate).item()  # type: ignore[union-attr]
            return float(prob)
        except Exception as exc:
            logger.debug("VAD inference error: %s", exc)
            return 0.0

    def reset(self) -> None:
        """Clear accumulated VAD state. Call at the start of each recording session."""
        self._speech_buf = []
        self._speech_samples = 0
        self._silence_samples = 0
        self._in_speech = False

    def flush(self) -> Generator[np.ndarray, None, None]:
        """Yield whatever speech has accumulated but not yet been emitted.

        Call this when recording stops to ensure the final utterance is not lost,
        even if the user stopped speaking before the silence threshold was reached.
        """
        if self._speech_buf and self._speech_samples >= self.min_speech_samples:
            # Trim any trailing silence frames
            if self._silence_samples > 0:
                trim = self._silence_samples // self._window_size
                trimmed = self._speech_buf[:-trim] if trim < len(self._speech_buf) else self._speech_buf
            else:
                trimmed = self._speech_buf
            if trimmed:
                segment = np.concatenate(trimmed).astype(np.float32)
                if segment.size >= self.min_speech_samples:
                    yield segment
        self.reset()

    def process_chunk(self, audio: np.ndarray) -> Generator[np.ndarray, None, None]:
        """Feed one audio chunk into the stateful VAD and yield completed speech segments.

        State (speech/silence accumulation) persists across calls so that speech
        spanning multiple chunks is assembled correctly before being emitted.

        Args:
            audio: 1-D float32 mono audio array from AudioCapture.drain_buffer()

        Yields:
            Complete speech segment arrays ready for Whisper transcription.
            A segment is emitted only after min_silence_duration_ms of silence
            follows at least min_speech_duration_ms of speech.
        """
        if not self.is_available():
            # Graceful fallback: accumulate raw audio across chunks and yield when
            # max_segment_sec is reached, using instance state so chunks aren't lost.
            self._speech_buf.append(audio)
            self._speech_samples += audio.size
            if self._speech_samples >= self.max_speech_samples:
                segment = np.concatenate(self._speech_buf).astype(np.float32)
                self._speech_buf = []
                self._speech_samples = 0
                yield segment
            return

        yield from self._process_windows(audio)

    def _process_windows(self, audio: np.ndarray) -> Generator[np.ndarray, None, None]:
        """Run VAD on each 512-sample window, updating persistent cross-chunk state."""
        # Pad to a multiple of the window size
        pad = (-len(audio)) % self._window_size
        if pad:
            audio = np.concatenate([audio, np.zeros(pad, dtype=np.float32)])

        for window in audio.reshape(-1, self._window_size):
            prob = self._vad_probability(window)
            is_speech = prob >= self.threshold

            if is_speech:
                self._speech_buf.append(window)
                self._speech_samples += self._window_size
                self._silence_samples = 0
                self._in_speech = True

                # Hard cap: force segment if speech has gone on too long without pause
                if self._speech_samples >= self.max_speech_samples:
                    segment = np.concatenate(self._speech_buf).astype(np.float32)
                    logger.debug("VAD max_segment cap hit (%ds) — forcing transcription", self.max_speech_samples // self.sample_rate)
                    yield segment
                    self.reset()

            elif self._in_speech:
                self._silence_samples += self._window_size
                self._speech_buf.append(window)  # keep trailing silence temporarily

                if self._silence_samples >= self.min_silence_samples:
                    # Trim the trailing silence frames we buffered
                    trim = self._silence_samples // self._window_size
                    trimmed = self._speech_buf[:-trim] if trim < len(self._speech_buf) else self._speech_buf
                    if trimmed:
                        segment = np.concatenate(trimmed).astype(np.float32)
                        if segment.size >= self.min_speech_samples:
                            yield segment
                    self.reset()

    def iter_segments(
        self,
        capture: AudioCapture,
        poll_interval: float = 0.05,
        stop_event: Optional[threading.Event] = None,
    ) -> Generator[np.ndarray, None, None]:
        """Continuously drain AudioCapture and yield VAD-confirmed speech segments.

        Maintains stateful VAD accumulation across chunks so that speech spanning
        multiple drain cycles is assembled correctly. Calls flush() at the end to
        emit any final utterance that hadn't yet hit the silence threshold.

        Args:
            capture: Active AudioCapture instance
            poll_interval: Seconds to sleep when the capture buffer is empty
            stop_event: When set, the generator drains remaining audio and exits

        Yields:
            Speech segment numpy arrays suitable for Whisper transcription
        """
        import time

        while stop_event is None or not stop_event.is_set():
            chunk = capture.drain_buffer()
            if chunk.size > 0:
                yield from self.process_chunk(chunk)
            else:
                time.sleep(poll_interval)

        # Drain any audio still in the capture buffer after stop
        chunk = capture.drain_buffer()
        if chunk.size > 0:
            yield from self.process_chunk(chunk)

        # Flush VAD-internal accumulated speech that never hit a silence boundary
        yield from self.flush()
