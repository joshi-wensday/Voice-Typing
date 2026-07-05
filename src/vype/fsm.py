"""Dictation state machine.

Pure logic — all timing is injected as millisecond timestamps, so the tap-vs-hold
decision is fully deterministic and testable.

Recording starts on key press either way; the release decides:
  released after >= tap_threshold_ms  → push-to-talk ended, process the audio
  released before the threshold       → it was a tap, stay recording hands-free
"""

from __future__ import annotations

from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    HELD_RECORDING = auto()
    HANDSFREE_RECORDING = auto()
    PROCESSING = auto()


class Command(Enum):
    NONE = auto()
    START_RECORDING = auto()
    STOP_AND_PROCESS = auto()
    CANCEL = auto()


class DictationFSM:
    def __init__(self, tap_threshold_ms: int = 300) -> None:
        self._threshold = tap_threshold_ms
        self._state = State.IDLE
        self._press_t: float | None = None

    @property
    def state(self) -> State:
        return self._state

    def on_press(self, t_ms: float) -> Command:
        if self._state is State.IDLE:
            self._state = State.HELD_RECORDING
            self._press_t = t_ms
            return Command.START_RECORDING
        if self._state is State.HANDSFREE_RECORDING:
            self._state = State.PROCESSING
            return Command.STOP_AND_PROCESS
        return Command.NONE

    def on_release(self, t_ms: float) -> Command:
        if self._state is not State.HELD_RECORDING:
            return Command.NONE
        held_for = t_ms - (self._press_t if self._press_t is not None else t_ms)
        if held_for >= self._threshold:
            self._state = State.PROCESSING
            return Command.STOP_AND_PROCESS
        self._state = State.HANDSFREE_RECORDING
        return Command.NONE

    def on_escape(self) -> Command:
        if self._state in (State.HELD_RECORDING, State.HANDSFREE_RECORDING):
            self._state = State.IDLE
            return Command.CANCEL
        return Command.NONE

    def on_processing_done(self) -> None:
        if self._state is State.PROCESSING:
            self._state = State.IDLE
