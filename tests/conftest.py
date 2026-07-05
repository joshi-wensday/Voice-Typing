"""Shared fakes: the whole pipeline is testable end-to-end with zero hardware."""

import numpy as np
import pytest

from vype.cleanup import CleanupUnavailable

SAMPLE_RATE = 16000


class FakeRecorder:
    """In-memory recorder; tests preload the audio that stop() will return."""

    def __init__(self, audio=None):
        self.audio = audio if audio is not None else np.zeros(SAMPLE_RATE, dtype=np.float32)
        self.is_recording = False
        self.level = 0.0
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.is_recording = True
        self.start_calls += 1

    def stop(self):
        self.is_recording = False
        self.stop_calls += 1
        return self.audio

    def snapshot(self, last_s=None):
        if last_s is None:
            return self.audio
        return self.audio[-int(last_s * SAMPLE_RATE):]


class FakeTranscriber:
    def __init__(self, text="hello world"):
        self.text = text
        self.loaded = False
        self.calls = []

    def load(self):
        self.loaded = True

    def transcribe(self, audio):
        self.calls.append(audio)
        return self.text


class FakeCleaner:
    def __init__(self, result="Hello, world.", fail=False):
        self.result = result
        self.fail = fail
        self.calls = []

    def clean(self, text):
        self.calls.append(text)
        if self.fail:
            raise CleanupUnavailable("offline")
        return self.result


class FakeInjector:
    def __init__(self):
        self.pasted = []

    def paste(self, text):
        self.pasted.append(text)


class FakeHistory:
    def __init__(self):
        self.records = []

    def append(self, raw, cleaned=None):
        self.records.append({"raw": raw, "cleaned": cleaned})


@pytest.fixture()
def fakes():
    return {
        "recorder": FakeRecorder(),
        "transcriber": FakeTranscriber(),
        "cleaner": FakeCleaner(),
        "injector": FakeInjector(),
        "history": FakeHistory(),
    }
