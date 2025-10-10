from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from vype.stt.whisper_engine import FasterWhisperEngine


@patch("vype.stt.whisper_engine.WhisperModel")
def test_preload_initializes_model(mock_model: MagicMock) -> None:
    engine = FasterWhisperEngine(model="base", device="cpu")
    assert engine._model is None
    engine.preload()
    assert engine._model is not None
    mock_model.assert_called_once()


@patch("vype.stt.whisper_engine.WhisperModel")
def test_transcribe_concatenates_segments(mock_model: MagicMock) -> None:
    # Mock segments iterator
    seg1 = SimpleNamespace(text="Hello")
    seg2 = SimpleNamespace(text="world")
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([seg1, seg2], SimpleNamespace(language="en"))
    mock_model.return_value = mock_instance

    engine = FasterWhisperEngine(model="base", device="cpu")
    audio = np.zeros(16000, dtype=np.float32)
    result = engine.transcribe(audio, sample_rate=16000)

    assert result.text == "Hello world"
    assert result.language == "en"
