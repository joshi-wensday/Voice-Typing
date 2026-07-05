"""Global hotkey listener built on the `keyboard` library.

Kept deliberately thin: OS key events in, debounced press/release callbacks out.
Windows auto-repeat fires key-down repeatedly while a key is held — only the
first down until the matching up is forwarded.
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


class HotkeyListener:
    def __init__(
        self,
        key: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        on_escape: Callable[[], None] | None = None,
    ) -> None:
        self._key = key
        self._on_press = on_press
        self._on_release = on_release
        self._on_escape = on_escape
        self._down = False
        self._hooks: list = []

    def start(self) -> None:
        import keyboard

        self._hooks.append(
            keyboard.on_press_key(self._key, self._handle_down, suppress=False)
        )
        self._hooks.append(
            keyboard.on_release_key(self._key, self._handle_up, suppress=False)
        )
        if self._on_escape is not None:
            self._hooks.append(
                keyboard.on_press_key("esc", lambda e: self._on_escape(), suppress=False)
            )
        logger.info("Hotkey registered: %s (hold = push-to-talk, tap = hands-free)", self._key)

    def stop(self) -> None:
        import keyboard

        for hook in self._hooks:
            try:
                keyboard.unhook(hook)
            except Exception:
                pass
        self._hooks.clear()

    def _handle_down(self, event) -> None:
        if self._down:
            return  # auto-repeat
        self._down = True
        self._on_press()

    def _handle_up(self, event) -> None:
        self._down = False
        self._on_release()
