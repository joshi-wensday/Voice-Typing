"""Long-audio splitting: cuts land in pauses, nothing exceeds the limit, a
failing piece costs only itself."""

import numpy as np
import pytest

from vype.chunking import GAP_MARKER, split_on_silence, transcribe_long

SR = 16000


def speech(seconds, amp=0.3):
    rng = np.random.default_rng(0)
    return (rng.standard_normal(int(seconds * SR)) * amp).astype(np.float32)


def silence(seconds):
    return np.zeros(int(seconds * SR), dtype=np.float32)


def test_short_audio_is_one_piece():
    audio = speech(5)
    pieces = split_on_silence(audio, SR, max_s=20)
    assert len(pieces) == 1 and pieces[0] is audio


def test_cut_lands_in_the_pause():
    # 14 s speech, 1 s pause, 14 s speech: the only sane cut is the pause
    audio = np.concatenate([speech(14), silence(1), speech(14)])
    pieces = split_on_silence(audio, SR, max_s=20)
    assert len(pieces) == 2
    cut_s = len(pieces[0]) / SR
    assert 14.0 <= cut_s <= 15.0


def test_pieces_never_exceed_limit_and_cover_everything():
    audio = speech(95)  # no pauses at all: still must split under the limit
    pieces = split_on_silence(audio, SR, max_s=20)
    assert all(len(p) <= 20 * SR for p in pieces)
    assert sum(len(p) for p in pieces) == len(audio)
    np.testing.assert_array_equal(np.concatenate(pieces), audio)


class ScriptedTranscriber:
    def __init__(self, fail_on=()):
        self.fail_on = set(fail_on)
        self.calls = 0

    def transcribe(self, audio):
        i = self.calls
        self.calls += 1
        if i in self.fail_on:
            raise RuntimeError("input too long")
        return f"part{i}"


def test_transcribe_long_joins_pieces():
    audio = np.concatenate([speech(14), silence(1), speech(14), silence(1), speech(14)])
    result = transcribe_long(ScriptedTranscriber(), audio, SR, max_chunk_s=20)
    assert result.text == "part0 part1 part2"
    assert result.complete and result.pieces == 3


def test_failed_piece_becomes_gap_not_total_loss():
    audio = np.concatenate([speech(14), silence(1), speech(14), silence(1), speech(14)])
    result = transcribe_long(ScriptedTranscriber(fail_on={1}), audio, SR, max_chunk_s=20)
    assert result.text == f"part0 {GAP_MARKER} part2"
    assert not result.complete and result.failed == 1


def test_all_pieces_failing_raises():
    with pytest.raises(RuntimeError):
        transcribe_long(ScriptedTranscriber(fail_on={0}), speech(3), SR, max_chunk_s=20)
