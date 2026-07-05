"""Dictation state machine: tap-vs-hold semantics, cancel, processing guard.

All timing is passed in explicitly (milliseconds) — no clocks, no sleeps.
"""

from vype.fsm import Command, DictationFSM, State

T = 300  # default tap threshold in ms


def make():
    return DictationFSM(tap_threshold_ms=T)


# ── Push-to-talk (hold) ──────────────────────────────────────────────────────

def test_press_from_idle_starts_recording():
    fsm = make()
    assert fsm.on_press(t_ms=0) == Command.START_RECORDING
    assert fsm.state == State.HELD_RECORDING


def test_release_after_threshold_stops_and_processes():
    fsm = make()
    fsm.on_press(t_ms=0)
    assert fsm.on_release(t_ms=T) == Command.STOP_AND_PROCESS
    assert fsm.state == State.PROCESSING


def test_release_just_under_threshold_goes_handsfree():
    fsm = make()
    fsm.on_press(t_ms=0)
    assert fsm.on_release(t_ms=T - 1) == Command.NONE
    assert fsm.state == State.HANDSFREE_RECORDING


# ── Hands-free (tap to start, tap to stop) ──────────────────────────────────

def test_tap_then_press_stops_handsfree():
    fsm = make()
    fsm.on_press(t_ms=0)
    fsm.on_release(t_ms=50)  # tap → hands-free
    assert fsm.on_press(t_ms=5000) == Command.STOP_AND_PROCESS
    assert fsm.state == State.PROCESSING
    # the release of that stopping press is a no-op
    assert fsm.on_release(t_ms=5040) == Command.NONE
    assert fsm.state == State.PROCESSING


# ── Processing guard ─────────────────────────────────────────────────────────

def test_press_during_processing_is_ignored():
    fsm = make()
    fsm.on_press(t_ms=0)
    fsm.on_release(t_ms=T)
    assert fsm.on_press(t_ms=1000) == Command.NONE
    assert fsm.state == State.PROCESSING


def test_processing_done_returns_to_idle():
    fsm = make()
    fsm.on_press(t_ms=0)
    fsm.on_release(t_ms=T)
    fsm.on_processing_done()
    assert fsm.state == State.IDLE
    assert fsm.on_press(t_ms=2000) == Command.START_RECORDING


def test_processing_done_when_idle_is_harmless():
    fsm = make()
    fsm.on_processing_done()
    assert fsm.state == State.IDLE


# ── Cancel ───────────────────────────────────────────────────────────────────

def test_escape_cancels_held_recording():
    fsm = make()
    fsm.on_press(t_ms=0)
    assert fsm.on_escape() == Command.CANCEL
    assert fsm.state == State.IDLE


def test_escape_cancels_handsfree_recording():
    fsm = make()
    fsm.on_press(t_ms=0)
    fsm.on_release(t_ms=10)
    assert fsm.on_escape() == Command.CANCEL
    assert fsm.state == State.IDLE


def test_escape_when_idle_or_processing_is_noop():
    fsm = make()
    assert fsm.on_escape() == Command.NONE
    fsm.on_press(t_ms=0)
    fsm.on_release(t_ms=T)
    assert fsm.on_escape() == Command.NONE
    assert fsm.state == State.PROCESSING


def test_release_after_escape_cancel_is_noop():
    """User holds key, hits Esc, then releases the hotkey."""
    fsm = make()
    fsm.on_press(t_ms=0)
    fsm.on_escape()
    assert fsm.on_release(t_ms=500) == Command.NONE
    assert fsm.state == State.IDLE


def test_full_cycle_twice():
    fsm = make()
    for start in (0, 10_000):
        assert fsm.on_press(t_ms=start) == Command.START_RECORDING
        assert fsm.on_release(t_ms=start + 400) == Command.STOP_AND_PROCESS
        fsm.on_processing_done()
    assert fsm.state == State.IDLE
