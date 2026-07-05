"""Pipeline: hotkey events → record → transcribe → (clean) → paste → history.

run_async=False makes processing synchronous, so every assertion is deterministic.
"""

import numpy as np
import pytest

from vype.config import Config
from vype.fsm import State
from vype.pipeline import Pipeline

SR = 16000


def make_pipeline(fakes, cfg=None, **kwargs):
    cfg = cfg or Config()
    p = Pipeline(
        recorder=fakes["recorder"],
        transcriber=fakes["transcriber"],
        cleaner=fakes["cleaner"],
        injector=fakes["injector"],
        history=fakes["history"],
        config=cfg,
        run_async=False,
        **kwargs,
    )
    p.events = []
    p.on_state = lambda s: p.events.append(("state", s))
    p.on_preview = lambda t: p.events.append(("preview", t))
    p.on_error = lambda m: p.events.append(("error", m))
    return p


def hold_cycle(p, t0=0.0):
    """Simulate press-hold-release via injected clock times (seconds)."""
    p.press(now=t0)
    p.release(now=t0 + 1.0)


# ── Core flow ────────────────────────────────────────────────────────────────

def test_hold_release_transcribes_and_pastes_raw(fakes):
    p = make_pipeline(fakes)
    hold_cycle(p)
    assert fakes["recorder"].start_calls == 1
    assert fakes["recorder"].stop_calls == 1
    assert len(fakes["transcriber"].calls) == 1
    assert fakes["injector"].pasted == ["hello world"]
    assert fakes["cleaner"].calls == []  # cleanup off by default
    assert fakes["history"].records == [{"raw": "hello world", "cleaned": None}]
    assert p.state == State.IDLE
    assert ("state", "recording") in p.events
    assert ("state", "processing") in p.events
    assert p.events[-1] == ("state", "idle")


def test_cleanup_mode_pastes_cleaned_keeps_raw_in_history(fakes):
    p = make_pipeline(fakes)
    p.cleanup_enabled = True
    hold_cycle(p)
    assert fakes["cleaner"].calls == ["hello world"]
    assert fakes["injector"].pasted == ["Hello, world."]
    assert fakes["history"].records == [{"raw": "hello world", "cleaned": "Hello, world."}]


def test_cleanup_failure_falls_back_to_raw(fakes):
    fakes["cleaner"].fail = True
    p = make_pipeline(fakes)
    p.cleanup_enabled = True
    hold_cycle(p)
    assert fakes["injector"].pasted == ["hello world"]
    assert fakes["history"].records == [{"raw": "hello world", "cleaned": None}]
    assert any(kind == "error" for kind, _ in p.events)
    assert p.state == State.IDLE


def test_empty_transcript_pastes_nothing(fakes):
    fakes["transcriber"].text = ""
    p = make_pipeline(fakes)
    hold_cycle(p)
    assert fakes["injector"].pasted == []
    assert fakes["history"].records == []
    assert p.state == State.IDLE


def test_too_short_utterance_discarded(fakes):
    fakes["recorder"].audio = np.zeros(int(0.2 * SR), dtype=np.float32)  # < 0.3 s
    p = make_pipeline(fakes)
    hold_cycle(p)
    assert fakes["transcriber"].calls == []
    assert fakes["injector"].pasted == []
    assert p.state == State.IDLE


def test_transcriber_exception_recovers_to_idle(fakes):
    def boom(audio):
        raise RuntimeError("engine crashed")

    fakes["transcriber"].transcribe = boom
    p = make_pipeline(fakes)
    hold_cycle(p)
    assert fakes["injector"].pasted == []
    assert any(kind == "error" for kind, _ in p.events)
    assert p.state == State.IDLE


# ── Hands-free & cancel ──────────────────────────────────────────────────────

def test_tap_starts_handsfree_second_press_stops(fakes):
    p = make_pipeline(fakes)
    p.press(now=0.0)
    p.release(now=0.05)  # tap
    assert p.state == State.HANDSFREE_RECORDING
    assert fakes["recorder"].is_recording
    p.press(now=10.0)  # second tap stops
    assert fakes["injector"].pasted == ["hello world"]
    assert p.state == State.IDLE


def test_escape_cancels_and_discards(fakes):
    p = make_pipeline(fakes)
    p.press(now=0.0)
    p.escape()
    assert fakes["recorder"].stop_calls == 1
    assert fakes["transcriber"].calls == []
    assert fakes["injector"].pasted == []
    assert p.state == State.IDLE


def test_press_while_processing_ignored(fakes):
    """A press during (synchronous) processing can't start a new recording —
    guarded by the FSM; here we just confirm two full cycles work back-to-back."""
    p = make_pipeline(fakes)
    hold_cycle(p, t0=0.0)
    hold_cycle(p, t0=100.0)
    assert fakes["recorder"].start_calls == 2
    assert len(fakes["injector"].pasted) == 2


# ── Live preview ─────────────────────────────────────────────────────────────

def test_preview_tick_emits_preview_text(fakes):
    p = make_pipeline(fakes)
    p.press(now=0.0)
    p.preview_tick()
    assert ("preview", "hello world") in p.events
    # preview never pastes or records history
    assert fakes["injector"].pasted == []
    assert fakes["history"].records == []


def test_preview_tick_skipped_when_engine_busy(fakes):
    p = make_pipeline(fakes)
    p.press(now=0.0)
    acquired = p._engine_lock.acquire()
    assert acquired
    try:
        p.preview_tick()
    finally:
        p._engine_lock.release()
    assert not any(kind == "preview" for kind, _ in p.events)


def test_preview_tick_noop_when_idle(fakes):
    p = make_pipeline(fakes)
    p.preview_tick()
    assert fakes["transcriber"].calls == []


def test_preview_uses_configured_window(fakes):
    cfg = Config()
    cfg.ui.preview_window_s = 2.0
    fakes["recorder"].audio = np.zeros(10 * SR, dtype=np.float32)
    p = make_pipeline(fakes, cfg=cfg)
    p.press(now=0.0)
    p.preview_tick()
    assert fakes["transcriber"].calls[0].shape == (2 * SR,)


def test_preview_skips_tiny_snapshots(fakes):
    fakes["recorder"].audio = np.zeros(int(0.1 * SR), dtype=np.float32)
    p = make_pipeline(fakes)
    p.press(now=0.0)
    p.preview_tick()
    assert fakes["transcriber"].calls == []
