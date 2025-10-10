"""Clipboard fallback strategy for text injection."""

from __future__ import annotations

try:
    import pyperclip  # type: ignore
except Exception:  # pragma: no cover
    pyperclip = None  # type: ignore

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover
    keyboard = None  # type: ignore

import time


class ClipboardStrategy:
    def is_available(self) -> bool:
        return pyperclip is not None and keyboard is not None

    def inject_text(self, text: str) -> bool:
        if not self.is_available():
            return False
        try:
            pyperclip.copy(text)
            time.sleep(0.01)
            keyboard.send("ctrl+v")
            return True
        except Exception:
            return False

    def press_key(self, key: str) -> bool:
        if keyboard is None:
            return False
        try:
            keyboard.send(key)
            return True
        except Exception:
            return False
