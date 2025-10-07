"""Command processor that extracts commands and returns cleaned text + commands.

Supports punctuation modes: auto, manual, hybrid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Tuple

from ..config.schema import AppConfig, CommandConfig, PunctuationMode
from .definitions import (
    Command,
    InsertTextCommand,
    NewLineCommand,
    PunctuationCommand,
    StopDictationCommand,
)


@dataclass
class Detected:
    pattern: re.Pattern[str]
    span: Tuple[int, int]
    command: Command


class CommandProcessor:
    """Processes raw text to extract voice commands and produce clean text."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._compile_patterns()

    def _get_mode(self) -> PunctuationMode:
        mode = self.config.punctuation.mode
        return mode if isinstance(mode, PunctuationMode) else PunctuationMode(mode)

    def _compile_patterns(self) -> None:
        cfg = self.config
        patterns: list[tuple[re.Pattern[str], Command, bool]] = []

        # Built-in control commands
        if cfg.commands.enabled and cfg.commands.new_line.enabled:
            patterns.append((re.compile(cfg.commands.new_line.pattern, re.IGNORECASE), NewLineCommand(), True))
        if cfg.commands.enabled and cfg.commands.stop_dictation.enabled:
            patterns.append((re.compile(cfg.commands.stop_dictation.pattern, re.IGNORECASE), StopDictationCommand(), True))

        # Always compile punctuation patterns so tokens can be removed from text.
        for _, c in cfg.punctuation.manual_commands.items():
            if not c.enabled:
                continue
            patterns.append((re.compile(c.pattern, re.IGNORECASE), PunctuationCommand(c.action), False))

        # Custom commands: treat action as literal insertion
        for _, cc in cfg.commands.custom_commands.items():
            if not cc.enabled:
                continue
            patterns.append((re.compile(cc.pattern, re.IGNORECASE), InsertTextCommand(cc.action), False))

        self._patterns = patterns

    def refresh(self, config: AppConfig) -> None:
        """Refresh processor with new configuration."""
        self.config = config
        self._compile_patterns()

    def process(self, text: str) -> tuple[str, list[Command]]:
        """Extract commands and return cleaned text and command list.

        Args:
            text: Raw transcription text

        Returns:
            Tuple of (cleaned_text, commands_to_execute)
        """
        if not text:
            return "", []

        matches: list[Detected] = []
        for pattern, command, _ in self._patterns:
            for m in pattern.finditer(text):
                matches.append(Detected(pattern=pattern, span=m.span(), command=command))

        if not matches:
            return text.strip(), []

        # Remove matched spans from text (from end to start to keep indices valid)
        matches.sort(key=lambda d: d.span[0])
        cleaned = []
        last_idx = 0
        for det in matches:
            start, end = det.span
            cleaned.append(text[last_idx:start])
            last_idx = end
        cleaned.append(text[last_idx:])
        cleaned_text = "".join(cleaned)

        # Normalize spaces
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

        # Determine final commands list based on punctuation mode
        mode = self._get_mode()
        if mode == PunctuationMode.HYBRID:
            filtered_cmds: list[Command] = []
            for det in matches:
                if isinstance(det.command, PunctuationCommand):
                    if cleaned_text.endswith(det.command.symbol):
                        # Whisper already provided punctuation; skip duplicate
                        continue
                filtered_cmds.append(det.command)
            commands = filtered_cmds
        elif mode == PunctuationMode.MANUAL:
            commands = [d.command for d in matches]
        else:
            # AUTO: remove manual punctuation commands
            commands = [d.command for d in matches if not isinstance(d.command, PunctuationCommand)]

        return cleaned_text, commands
