"""Global hotkey registration using the `keyboard` library."""

from __future__ import annotations

from typing import Callable

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover
    keyboard = None  # type: ignore


class HotkeyManager:
    def __init__(self, hotkey: str, on_toggle: Callable[[], None]) -> None:
        self.hotkey = hotkey
        self.on_toggle = on_toggle
        self._registered = False

    def is_available(self) -> bool:
        return keyboard is not None

    def register(self) -> bool:
        if not self.is_available():
            return False
        if self._registered:
            return True
        try:
            keyboard.add_hotkey(self.hotkey, self.on_toggle, suppress=False, trigger_on_release=True)
            self._registered = True
            return True
        except Exception:
            return False

    def wait(self) -> None:
        if not self.is_available():
            return
        keyboard.wait()
