"""Text injection: clipboard snapshot → set → Ctrl+V → conditional restore.

The clipboard is restored only if it still holds our pasted text, so a copy the
user made in the meantime is never clobbered.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Protocol

logger = logging.getLogger(__name__)


class Clipboard(Protocol):
    def read(self) -> str: ...
    def write(self, text: str) -> None: ...


class Keys(Protocol):
    def send(self, combo: str) -> None: ...


class PyperclipClipboard:
    def read(self) -> str:
        import pyperclip

        return pyperclip.paste()

    def write(self, text: str) -> None:
        import pyperclip

        pyperclip.copy(text)


class KeyboardKeys:
    def send(self, combo: str) -> None:
        import keyboard

        keyboard.send(combo)


def _timer_schedule(delay_s: float, fn: Callable[[], None]) -> None:
    t = threading.Timer(delay_s, fn)
    t.daemon = True
    t.start()


class Injector:
    def __init__(
        self,
        clipboard: Clipboard | None = None,
        keys: Keys | None = None,
        restore_delay_s: float = 1.0,
        schedule: Callable[[float, Callable[[], None]], None] = _timer_schedule,
    ) -> None:
        self._clipboard = clipboard or PyperclipClipboard()
        self._keys = keys or KeyboardKeys()
        self._restore_delay_s = restore_delay_s
        self._schedule = schedule

    def paste(self, text: str) -> None:
        if not text:
            return
        try:
            previous: str | None = self._clipboard.read()
        except Exception as exc:
            logger.warning("Could not snapshot clipboard: %s", exc)
            previous = None

        self._clipboard.write(text)
        self._keys.send("ctrl+v")

        if previous is not None:
            self._schedule(self._restore_delay_s, lambda: self._restore(previous, text))

    def _restore(self, previous: str, pasted: str) -> None:
        try:
            if self._clipboard.read() == pasted:
                self._clipboard.write(previous)
        except Exception as exc:
            logger.warning("Clipboard restore failed: %s", exc)
