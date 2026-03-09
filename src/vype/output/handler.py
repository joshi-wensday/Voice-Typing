"""Output handler that injects text and sends key-presses via strategies."""

from __future__ import annotations

from ..config.schema import AppConfig
from .strategies.keyboard import KeyboardStrategy
from .strategies.uia import UIAStrategy
from .strategies.clipboard import ClipboardStrategy


class OutputHandler:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        speed = config.output.typing_speed
        self._strategies = self._build_strategies(speed)
        self._clipboard = ClipboardStrategy()

    def _build_strategies(self, typing_speed: float) -> list:
        order = []
        primary = self.config.output.primary_method
        fallback = list(self.config.output.fallback_methods)
        methods = [primary] + [m for m in fallback if m != primary]

        for name in methods:
            if name == "keyboard":
                order.append(KeyboardStrategy(typing_speed))
            elif name == "uia":
                order.append(UIAStrategy())
            elif name == "clipboard":
                order.append(ClipboardStrategy())
        return order

    def inject_text(self, text: str) -> bool:
        """Type text into the focused application."""
        # Prefer clipboard for long text to reduce latency
        if (
            len(text) >= self.config.output.prefer_clipboard_over_chars
            and self._clipboard.is_available()
        ):
            if self._clipboard.inject_text(text):
                return True
        for strat in self._strategies:
            if getattr(strat, "is_available")() and strat.inject_text(text):
                return True
        return False

    def press_key(self, key: str) -> bool:
        """Send a key-press (e.g. 'backspace', 'ctrl+z') to the focused application."""
        for strat in self._strategies:
            if getattr(strat, "is_available")() and strat.press_key(key):
                return True
        return False
