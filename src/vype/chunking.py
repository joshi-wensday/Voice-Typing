"""Long-audio safety: split at natural pauses, transcribe piecewise, join.

STT engines have an input ceiling (Parakeet's attention cost / VRAM, Whisper's
30 s window, API upload limits). Rather than make the user aware of it, long
recordings are cut at the quietest point inside each window and the pieces are
transcribed one by one. A piece that fails becomes a visible gap marker instead
of costing the whole recording.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

GAP_MARKER = "[…]"

_FRAME_S = 0.02  # energy frame
_SMOOTH_FRAMES = 15  # ~300 ms moving average — a "pause", not a stop consonant


def split_on_silence(
    audio: np.ndarray, sample_rate: int, max_s: float, min_s: float | None = None
) -> list[np.ndarray]:
    """Cut `audio` into pieces no longer than `max_s`, each cut at the quietest
    ~300 ms stretch between `min_s` (default max_s / 2) and `max_s` into the
    piece. Audio that already fits is returned as a single piece."""
    n = len(audio)
    max_n = int(max_s * sample_rate)
    if max_n <= 0 or n <= max_n:
        return [audio]
    min_n = int((max_s / 2 if min_s is None else min_s) * sample_rate)

    pieces: list[np.ndarray] = []
    start = 0
    while n - start > max_n:
        cut = _next_cut(audio, start, sample_rate, max_n, min_n)
        pieces.append(audio[start:cut])
        start = cut
    pieces.append(audio[start:])
    return pieces


def _frame_len(sample_rate: int) -> int:
    return max(1, int(_FRAME_S * sample_rate))


def lookahead_samples(sample_rate: int) -> int:
    """Audio needed past a window before its cut is final: the smoothing reads
    this far ahead, and a buffer edge would otherwise look like a pause."""
    return (_SMOOTH_FRAMES + 1) * _frame_len(sample_rate)


def _next_cut(audio: np.ndarray, start: int, sample_rate: int, max_n: int, min_n: int) -> int:
    """Where the piece starting at `start` should end. Depends only on the
    audio in [start, start + max_n + lookahead), and frames are aligned to
    `start` — so a live (still-growing) recording gets the same cut as the
    finished one."""
    frame = _frame_len(sample_rate)
    seg = audio[start : start + max_n + lookahead_samples(sample_rate)]
    n_frames = len(seg) // frame
    energy = (seg[: n_frames * frame].astype(np.float32).reshape(n_frames, frame) ** 2).mean(axis=1)
    smooth = np.convolve(energy, np.ones(_SMOOTH_FRAMES) / _SMOOTH_FRAMES, mode="same")
    lo = min_n // frame
    hi = min(max_n // frame, n_frames)  # exclusive; keeps cut < start + max_n
    if hi <= lo:
        return start + max_n
    # latest of the quietest frames → pieces stay as long as allowed
    f = hi - 1 - int(np.argmin(smooth[lo:hi][::-1]))
    return start + f * frame + frame // 2


@dataclass
class LongTranscript:
    text: str
    pieces: int
    failed: int

    @property
    def complete(self) -> bool:
        return self.failed == 0


class IncrementalTranscript:
    """Transcribe a recording piece by piece *while it is still growing*.

    `advance(audio_so_far)` commits the next piece only once the audio extends
    past a full max-length window, so the cut it picks is exactly the cut
    `split_on_silence` would pick on the finished recording. `finish(audio)`
    transcribes whatever is left — on a long dictation that's just the last few
    seconds, so the result is ready almost the moment you stop.

    `transcribe` is any callable audio → text (the pipeline wraps the engine
    lock around it).
    """

    def __init__(self, transcribe, sample_rate: int, max_chunk_s: float) -> None:
        self._transcribe = transcribe
        self._sr = sample_rate
        self._max_s = max_chunk_s
        self._max_n = int(max_chunk_s * sample_rate)
        self.offset = 0  # samples already committed
        self._texts: list[str] = []
        self._pieces = 0
        self._failed = 0
        self._last_exc: Exception | None = None

    @property
    def committed_pieces(self) -> int:
        return self._pieces

    def ready(self, total_samples: int) -> bool:
        """Cheap check: is there a full window beyond the committed point?"""
        return total_samples - self.offset >= self._max_n + lookahead_samples(self._sr)

    def advance(self, audio: np.ndarray) -> bool:
        """Commit one piece if one is final. Returns True if it did."""
        if not self.ready(len(audio)):
            return False
        cut = _next_cut(audio, self.offset, self._sr, self._max_n, self._max_n // 2)
        self._run(audio[self.offset : cut])
        self.offset = cut
        return True

    def finish(self, audio: np.ndarray) -> LongTranscript:
        """Transcribe the rest. Raises only if *every* piece failed."""
        rest = audio[self.offset :]
        pieces = split_on_silence(rest, self._sr, self._max_s) if len(rest) else []
        if self._pieces + len(pieces) > 1:
            logger.info(
                "Recording %.1f s: %d pieces done during recording, %d at the end",
                len(audio) / self._sr,
                self._pieces,
                len(pieces),
            )
        for piece in pieces:
            self._run(piece)
        self.offset = len(audio)
        if self._pieces and self._failed == self._pieces and self._last_exc is not None:
            raise self._last_exc
        if self._pieces == 1:  # untouched: engines' own whitespace is meaningful
            return LongTranscript(text=self._texts[0], pieces=1, failed=self._failed)
        text = " ".join(t.strip() for t in self._texts if t.strip())
        return LongTranscript(text=text, pieces=self._pieces, failed=self._failed)

    def _run(self, piece: np.ndarray) -> None:
        self._pieces += 1
        try:
            text = self._transcribe(piece)
        except Exception as exc:
            logger.warning("Piece %d failed: %s", self._pieces, exc)
            self._failed += 1
            self._last_exc = exc
            self._texts.append(GAP_MARKER)
            return
        self._texts.append(text or "")


def transcribe_long(
    transcriber, audio: np.ndarray, sample_rate: int, max_chunk_s: float
) -> LongTranscript:
    """Transcribe audio of any length in one go. Raises only if every piece fails."""
    return IncrementalTranscript(transcriber.transcribe, sample_rate, max_chunk_s).finish(audio)
