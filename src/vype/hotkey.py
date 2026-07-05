"""Global hotkey listener built on the `keyboard` library.

Supports single keys ("f8") and combos ("ctrl+alt"): press fires when every key
in the combo is down, release fires when any of them lifts. Left/right modifier
variants are normalized, so "ctrl" matches either Ctrl key. Windows auto-repeat
is debounced — only the first down until the matching up is forwarded.

_on_event contains all the logic and takes plain event objects, so it is fully
unit-testable without hooking the real keyboard.
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

_CANONICAL = {
    "left ctrl": "ctrl",
    "right ctrl": "ctrl",
    "left alt": "alt",
    "right alt": "alt",
    "alt gr": "alt",
    "left shift": "shift",
    "right shift": "shift",
    "left windows": "windows",
    "right windows": "windows",
}


def _canonical(name: str) -> str:
    return _CANONICAL.get(name.lower(), name.lower())


class HotkeyListener:
    def __init__(
        self,
        key: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        on_escape: Callable[[], None] | None = None,
    ) -> None:
        self._spec = key
        self._combo = frozenset(_canonical(part.strip()) for part in key.split("+") if part.strip())
        self._on_press = on_press
        self._on_release = on_release
        self._on_escape = on_escape
        self._down: set[str] = set()
        self._active = False
        self._hook = None

    def start(self) -> None:
        import keyboard

        self._hook = keyboard.hook(self._on_event)
        logger.info("Hotkey registered: %s (hold = push-to-talk, tap = hands-free)", self._spec)

    def stop(self) -> None:
        if self._hook is not None:
            import keyboard

            try:
                keyboard.unhook(self._hook)
            except Exception:
                pass
            self._hook = None
        self._down.clear()
        self._active = False

    def _on_event(self, event) -> None:
        name = event.name
        if not name:
            return
        key = _canonical(name)

        if event.event_type == "down":
            if key == "esc":
                if self._on_escape is not None:
                    self._on_escape()
                return
            if key not in self._combo:
                return
            self._down.add(key)
            if not self._active and self._down >= self._combo:
                self._active = True
                self._on_press()
        else:  # up
            if key not in self._combo:
                return
            self._down.discard(key)
            if self._active:
                self._active = False
                self._on_release()
