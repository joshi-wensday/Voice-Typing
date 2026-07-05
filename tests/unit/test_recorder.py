"""Recorder: buffering, snapshot windows, level metering — with a fake stream."""

import numpy as np
import pytest

from vype.recorder import Recorder


class FakeStream:
    def __init__(self):
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


@pytest.fixture()
def recorder():
    streams = []

    def factory(samplerate, channels, device, callback):
        assert samplerate == 16000
        assert channels == 1
        stream = FakeStream()
        stream.callback = callback
        streams.append(stream)
        return stream

    r = Recorder(sample_rate=16000, device_id=None, stream_factory=factory)
    r._test_streams = streams
    return r


def chunk(value, n=1600):
    return np.full(n, value, dtype=np.float32)


def test_stop_returns_concatenated_audio(recorder):
    recorder.start()
    stream = recorder._test_streams[0]
    stream.callback(chunk(0.1))
    stream.callback(chunk(0.2))
    audio = recorder.stop()
    assert audio.shape == (3200,)
    assert audio[0] == pytest.approx(0.1)
    assert audio[-1] == pytest.approx(0.2)
    assert stream.closed


def test_stop_without_audio_returns_empty(recorder):
    recorder.start()
    audio = recorder.stop()
    assert audio.shape == (0,)


def test_start_clears_previous_session(recorder):
    recorder.start()
    recorder._test_streams[0].callback(chunk(0.5))
    recorder.stop()
    recorder.start()
    audio = recorder.stop()
    assert audio.shape == (0,)


def test_snapshot_returns_tail_window(recorder):
    recorder.start()
    stream = recorder._test_streams[0]
    for v in (0.1, 0.2, 0.3, 0.4):
        stream.callback(chunk(v, n=16000))  # 1 s each
    snap = recorder.snapshot(last_s=2.0)
    assert snap.shape == (32000,)
    assert snap[0] == pytest.approx(0.3)
    assert snap[-1] == pytest.approx(0.4)
    # snapshot does not consume the buffer
    assert recorder.stop().shape == (64000,)


def test_snapshot_full_when_no_window(recorder):
    recorder.start()
    recorder._test_streams[0].callback(chunk(0.1, n=16000))
    assert recorder.snapshot().shape == (16000,)


def test_level_reflects_amplitude(recorder):
    recorder.start()
    stream = recorder._test_streams[0]
    assert recorder.level == 0.0
    stream.callback(chunk(0.5))
    loud = recorder.level
    assert 0.0 < loud <= 1.0
    recorder.stop()
    assert recorder.level == 0.0


def test_is_recording_flag(recorder):
    assert not recorder.is_recording
    recorder.start()
    assert recorder.is_recording
    recorder.stop()
    assert not recorder.is_recording
