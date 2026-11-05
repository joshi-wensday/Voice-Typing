"""Never lose a recording: mic audio streams to disk while you speak.

Each recording is a raw 16-bit PCM file in ~/.vype/pending/. It is deleted only
once its transcript has been pasted and saved to history (or the user cancelled
on purpose). Anything still on disk afterwards — a failed transcription, a crash
mid-recording — can be transcribed later via `pending()` + `load()`.

Writes happen on a dedicated thread so a slow disk can never stall the audio
callback.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

SUFFIX = ".pcm"


class SpoolRecording:
    """One open recording file. write() is cheap and safe from the audio thread."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue()
        self._file = path.open("wb")
        self._thread = threading.Thread(target=self._drain, daemon=True, name="vype-spool")
        self._thread.start()

    def write(self, chunk: np.ndarray) -> None:
        self._queue.put(chunk)

    def close(self) -> None:
        """Flush everything queued so far and close the file (blocks briefly)."""
        self._queue.put(None)
        self._thread.join(timeout=5.0)

    def _drain(self) -> None:
        try:
            while True:
                chunk = self._queue.get()
                if chunk is None:
                    break
                pcm = np.clip(chunk * 32767.0, -32768, 32767).astype("<i2")
                self._file.write(pcm.tobytes())
                self._file.flush()  # survives an app crash (not a power cut — fine)
        except Exception as exc:
            logger.error("Audio spool write failed (%s): %s", self.path, exc)
        finally:
            self._file.close()


class AudioSpool:
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._active: set[Path] = set()
        self._lock = threading.Lock()

    def begin(self) -> SpoolRecording | None:
        """Open a new recording file. Returns None (and logs) if the disk refuses —
        dictation must still work without the safety net."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._dir / f"{time.time_ns()}{SUFFIX}"
            rec = SpoolRecording(path)
        except Exception as exc:
            logger.error("Could not open audio spool: %s", exc)
            return None
        with self._lock:
            self._active.add(path)
        return rec

    def release(self, rec: SpoolRecording) -> None:
        """Recording is no longer in flight (its file may stay as pending)."""
        with self._lock:
            self._active.discard(rec.path)

    def discard(self, path: Path) -> None:
        with self._lock:
            self._active.discard(path)
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Could not delete spooled audio %s: %s", path, exc)

    def pending(self) -> list[Path]:
        """Saved recordings not currently being recorded/processed, oldest first."""
        if not self._dir.exists():
            return []
        with self._lock:
            active = set(self._active)
        return sorted(
            (p for p in self._dir.glob(f"*{SUFFIX}") if p not in active),
            key=lambda p: p.name,
        )

    @staticmethod
    def load(path: Path) -> np.ndarray:
        data = Path(path).read_bytes()
        data = data[: len(data) - len(data) % 2]  # a crash can leave half a sample
        return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0

    @staticmethod
    def recorded_at(path: Path) -> float:
        try:
            return int(Path(path).stem) / 1e9
        except ValueError:
            return Path(path).stat().st_mtime
