"""Keyboard strategy for text injection using the `keyboard` library.

Note: In tests, calls to keyboard are mocked.
"""

from __future__ import annotations

import time
from typing import Optional

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover - on environments without keyboard
    keyboard = None  # type: ignore


class KeyboardStrategy:
    """Simulate typing via keyboard.write and sending keys."""

    def __init__(self, typing_speed: float = 0.01) -> None:
        self.typing_speed = typing_speed

    def is_available(self) -> bool:
        return keyboard is not None

    def inject_text(self, text: str) -> bool:
        if not self.is_available():
            return False
        try:
            keyboard.write(text, delay=self.typing_speed)
            return True
        except Exception:
            return False

    def press_key(self, key: str) -> bool:
        if not self.is_available():
            return False
        try:
            keyboard.send(key)
            return True
        except Exception:
            return False
