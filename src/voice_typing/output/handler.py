"""Output handler that injects text and executes commands via strategies."""

from __future__ import annotations

from typing import Iterable, List

from ..config.schema import AppConfig
from ..commands.definitions import Command, InsertTextCommand, NewLineCommand, PunctuationCommand
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
        # Prefer clipboard for long text to reduce latency
        if len(text) >= self.config.output.prefer_clipboard_over_chars and self._clipboard.is_available():
            if self._clipboard.inject_text(text):
                return True
        for strat in self._strategies:
            if getattr(strat, "is_available")() and strat.inject_text(text):
                return True
        return False

    def press_key(self, key: str) -> bool:
        for strat in self._strategies:
            if getattr(strat, "is_available")() and strat.press_key(key):
                return True
        return False

    def execute_command(self, command: Command) -> bool:
        if isinstance(command, InsertTextCommand):
            return self.inject_text(command.text)
        if isinstance(command, NewLineCommand):
            return self.inject_text("\n")
        if isinstance(command, PunctuationCommand):
            return self.inject_text(command.symbol)
        return True
