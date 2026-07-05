"""Real-model integration tests. Run locally: pytest -m gpu

These need model weights (downloaded on first run) and a CUDA GPU.
Speech fixtures: drop short WAVs (16 kHz mono) into tests/fixtures/ named
<anything>.wav with a sibling <anything>.txt containing the expected words,
and test_fixture_transcription will pick them up.
"""

from pathlib import Path

import numpy as np
import pytest

from vype.config import SttConfig
from vype.stt import create_transcriber

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def parakeet():
    t = create_transcriber(SttConfig(backend="parakeet"))
    t.load()
    return t


@pytest.mark.gpu
def test_load_and_transcribe_silence(parakeet):
    """Model loads and inference runs; silence must not hallucinate words."""
    silence = np.zeros(16000, dtype=np.float32)
    text = parakeet.transcribe(silence)
    assert isinstance(text, str)
    assert len(text.split()) <= 2  # allow at most trivial noise output


@pytest.mark.gpu
@pytest.mark.parametrize(
    "wav", sorted(FIXTURES.glob("*.wav")) or [pytest.param(None, marks=pytest.mark.skip)]
)
def test_fixture_transcription(parakeet, wav):
    import wave as wave_mod

    with wave_mod.open(str(wav), "rb") as wf:
        assert wf.getframerate() == 16000, "fixtures must be 16 kHz mono"
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    audio = pcm.astype(np.float32) / 32768.0

    expected = wav.with_suffix(".txt").read_text(encoding="utf-8").lower().split()
    got = parakeet.transcribe(audio).lower()

    missing = [w for w in expected if w.strip(".,!?") not in got]
    assert len(missing) <= max(1, len(expected) // 10), f"missing words: {missing}"


@pytest.mark.gpu
def test_transcription_latency_budget(parakeet):
    """30 s of audio must transcribe fast enough for the 1.5 s preview cadence."""
    import time

    audio = (np.random.default_rng(0).standard_normal(30 * 16000) * 0.01).astype(np.float32)
    parakeet.transcribe(audio)  # warm-up
    t0 = time.perf_counter()
    parakeet.transcribe(audio)
    assert time.perf_counter() - t0 < 1.0
