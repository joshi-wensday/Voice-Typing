"""Audio spool round-trip and pending bookkeeping (real files, tmp dir)."""

import numpy as np

from vype.spool import AudioSpool


def test_round_trip_and_pending(tmp_path):
    spool = AudioSpool(tmp_path)
    rec = spool.begin()
    chunk = np.linspace(-0.5, 0.5, 1600, dtype=np.float32)
    rec.write(chunk)
    rec.write(chunk)

    assert spool.pending() == []  # in flight: not up for recovery
    rec.close()
    spool.release(rec)
    assert spool.pending() == [rec.path]

    loaded = AudioSpool.load(rec.path)
    assert len(loaded) == 3200
    np.testing.assert_allclose(loaded[:1600], chunk, atol=1e-4)

    spool.discard(rec.path)
    assert spool.pending() == []


def test_load_tolerates_torn_final_sample(tmp_path):
    path = tmp_path / "123.pcm"
    path.write_bytes(b"\x00\x40\x00\x40\x01")  # 2.5 samples — crash mid-write
    assert len(AudioSpool.load(path)) == 2


def test_begin_returns_none_when_disk_refuses(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert AudioSpool(blocker / "sub").begin() is None
