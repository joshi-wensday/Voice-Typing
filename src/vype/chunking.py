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

    frame = max(1, int(_FRAME_S * sample_rate))
    n_frames = n // frame
    energy = (audio[: n_frames * frame].astype(np.float32).reshape(n_frames, frame) ** 2).mean(axis=1)
    smooth = np.convolve(energy, np.ones(_SMOOTH_FRAMES) / _SMOOTH_FRAMES, mode="same")

    pieces: list[np.ndarray] = []
    start = 0
    while n - start > max_n:
        lo = (start + min_n) // frame
        hi = min((start + max_n) // frame, n_frames)  # exclusive; keeps cut < start + max_n
        if hi <= lo:
            cut = start + max_n
        else:
            window = smooth[lo:hi]
            # latest of the quietest frames → pieces stay as long as allowed
            f = hi - 1 - int(np.argmin(window[::-1]))
            cut = f * frame + frame // 2
        pieces.append(audio[start:cut])
        start = cut
    pieces.append(audio[start:])
    return pieces


@dataclass
class LongTranscript:
    text: str
    pieces: int
    failed: int

    @property
    def complete(self) -> bool:
        return self.failed == 0


def transcribe_long(
    transcriber, audio: np.ndarray, sample_rate: int, max_chunk_s: float
) -> LongTranscript:
    """Transcribe audio of any length. Raises only if *every* piece fails."""
    pieces = split_on_silence(audio, sample_rate, max_chunk_s)
    if len(pieces) > 1:
        logger.info(
            "Long recording (%.1f s) split into %d pieces", len(audio) / sample_rate, len(pieces)
        )
    texts: list[str] = []
    failed = 0
    last_exc: Exception | None = None
    for i, piece in enumerate(pieces):
        try:
            text = transcriber.transcribe(piece)
        except Exception as exc:
            logger.warning("Piece %d/%d failed: %s", i + 1, len(pieces), exc)
            failed += 1
            last_exc = exc
            texts.append(GAP_MARKER)
            continue
        if text:
            texts.append(text if len(pieces) == 1 else text.strip())
    if failed == len(pieces) and last_exc is not None:
        raise last_exc
    if len(pieces) == 1:  # untouched: engines' own whitespace is meaningful
        return LongTranscript(text=texts[0] if texts else "", pieces=1, failed=failed)
    return LongTranscript(text=" ".join(t for t in texts if t), pieces=len(pieces), failed=failed)
