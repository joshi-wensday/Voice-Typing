"""Unit tests for CanaryQwenEngine."""

from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from vype.stt.canary_engine import CanaryQwenEngine, TranscriptionResult, _apply_itn


# ---------------------------------------------------------------------------
# ITN helper tests (no model required)
# ---------------------------------------------------------------------------

def test_itn_dollars() -> None:
    assert _apply_itn("that costs 5 dollars") == "that costs $5"


def test_itn_percent() -> None:
    assert _apply_itn("50 percent discount") == "50% discount"


def test_itn_no_change() -> None:
    text = "Hello, world."
    assert _apply_itn(text) == text


def test_itn_mister() -> None:
    assert _apply_itn("mister Smith") == "Mr. Smith"


def test_itn_doctor() -> None:
    assert _apply_itn("doctor Jones") == "Dr. Jones"


# ---------------------------------------------------------------------------
# Engine lifecycle (model mocked)
# ---------------------------------------------------------------------------

@patch("vype.stt.canary_engine.SALM", create=True)
def test_preload_initializes_model(MockSALM) -> None:
    """preload() should call SALM.from_pretrained exactly once."""
    mock_instance = MagicMock()
    mock_instance.eval = MagicMock(return_value=mock_instance)
    mock_instance.to = MagicMock(return_value=mock_instance)
    MockSALM.from_pretrained.return_value = mock_instance

    with patch.dict("sys.modules", {
        "torch": MagicMock(),
        "nemo": MagicMock(),
        "nemo.collections": MagicMock(),
        "nemo.collections.speechlm2": MagicMock(),
        "nemo.collections.speechlm2.models": MagicMock(SALM=MockSALM),
    }):
        engine = CanaryQwenEngine(device="cpu")
        assert engine._model is None
        engine.preload()
        assert engine._model is not None
        MockSALM.from_pretrained.assert_called_once_with("nvidia/canary-qwen-2.5b")


def test_preload_noop_when_already_loaded() -> None:
    """preload() should be a no-op if model is already loaded."""
    engine = CanaryQwenEngine(device="cpu")
    engine._model = MagicMock()  # simulate already loaded
    # _ensure_imports would fail if called, but it shouldn't be
    engine.preload()
    # No exception = pass


def test_reset_context_clears_tail() -> None:
    engine = CanaryQwenEngine()
    engine._context_tail = "some prior text"
    engine.reset_context()
    assert engine._context_tail == ""


def test_transcribe_incremental_empty_audio() -> None:
    """Empty audio should return empty string without loading model."""
    engine = CanaryQwenEngine()
    result = engine.transcribe_incremental(np.array([], dtype=np.float32))
    assert result == ""


def test_transcribe_requires_16khz() -> None:
    engine = CanaryQwenEngine()
    engine._model = MagicMock()
    with pytest.raises(ValueError, match="16 kHz"):
        engine.transcribe_incremental(np.zeros(8000, dtype=np.float32), sample_rate=8000)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def test_build_prompt_without_context() -> None:
    engine = CanaryQwenEngine(enable_pnc=True)
    engine._model = MagicMock()
    engine._model.audio_locator_tag = "<|audio|>"
    prompt = engine._build_prompt("")
    assert "<|audio|>" in prompt
    assert "punctuation" in prompt.lower()
    assert "Prior context" not in prompt


def test_build_prompt_with_context() -> None:
    engine = CanaryQwenEngine(enable_pnc=False)
    engine._model = MagicMock()
    engine._model.audio_locator_tag = "<|audio|>"
    prompt = engine._build_prompt("some prior text")
    assert "Prior context" in prompt
    assert "some prior text" in prompt


# ---------------------------------------------------------------------------
# TranscriptionResult
# ---------------------------------------------------------------------------

def test_transcription_result_fields() -> None:
    r = TranscriptionResult(text="Hello world", language="en")
    assert r.text == "Hello world"
    assert r.language == "en"


def test_get_supported_models() -> None:
    engine = CanaryQwenEngine()
    models = engine.get_supported_models()
    assert "nvidia/canary-qwen-2.5b" in models
    assert len(models) >= 3
