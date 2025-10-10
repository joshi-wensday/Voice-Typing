"""Command definitions used by the command processor.

Commands are returned by the processor and later executed by the output handler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class OutputExecutor(Protocol):
    """Protocol for output handler execution used by commands."""

    def inject_text(self, text: str) -> bool:  # pragma: no cover - implemented in Phase 4
        ...

    def press_key(self, key: str) -> bool:  # pragma: no cover - implemented in Phase 4
        ...


@dataclass(frozen=True)
class Command:
    """Base command type."""

    def execute(self, executor: OutputExecutor) -> bool:  # pragma: no cover
        return True


@dataclass(frozen=True)
class InsertTextCommand(Command):
    """Insert literal text at the cursor position."""

    text: str

    def execute(self, executor: OutputExecutor) -> bool:  # pragma: no cover
        return executor.inject_text(self.text)


@dataclass(frozen=True)
class NewLineCommand(Command):
    """Insert a line break."""

    def execute(self, executor: OutputExecutor) -> bool:  # pragma: no cover
        return executor.inject_text("\n")


@dataclass(frozen=True)
class StopDictationCommand(Command):
    """Signal to stop the dictation session."""

    def execute(self, executor: OutputExecutor) -> bool:  # pragma: no cover
        return True


@dataclass(frozen=True)
class PunctuationCommand(Command):
    """Insert a punctuation symbol (e.g., '.', ',', '?', '!')."""

    symbol: str

    def execute(self, executor: OutputExecutor) -> bool:  # pragma: no cover
        return executor.inject_text(self.symbol)
