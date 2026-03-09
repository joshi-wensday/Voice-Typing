"""Command Executor Skill: maps LLM tool labels to system actions.

This skill replaces the regex-only CommandProcessor for commands that arrive
via the Intent Router's COMMAND classification. It maps structured tool names
(DELETE_WORD, NEW_LINE, etc.) to concrete keyboard/output actions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillCommand:
    """A resolved command ready for execution."""

    tool: str
    description: str = ""


# Type alias for the executor callbacks provided by OutputHandler
_Injector = Callable[[str], bool]
_KeyPresser = Callable[[str], bool]


class CommandExecutor:
    """Executes system commands mapped from LLM tool names.

    Accepts an inject_text callable and a press_key callable from the
    OutputHandler so this skill stays decoupled from the output layer.
    """

    # Mapping from tool name to (action_type, value)
    # action_type: "key" = single keystroke/combo, "text" = inject text, "special" = custom
    _TOOL_MAP: dict[str, tuple[str, str]] = {
        "DELETE_WORD": ("key", "ctrl+backspace"),
        "DELETE_LINE": ("key", "shift+home, backspace"),
        "NEW_LINE": ("text", "\n"),
        "NEW_PARAGRAPH": ("text", "\n\n"),
        "SAVE": ("key", "ctrl+s"),
        "UNDO": ("key", "ctrl+z"),
        "BULLET_POINT": ("text", "\n• "),
        "STOP": ("special", "STOP"),
        "SCRATCH_THAT": ("special", "SCRATCH_THAT"),
        "DELETE_SENTENCE": ("special", "DELETE_SENTENCE"),
        "CAPITALIZE": ("special", "CAPITALIZE"),
        "LOWERCASE": ("special", "LOWERCASE"),
    }

    def __init__(
        self,
        inject_text: _Injector,
        press_key: _KeyPresser,
        stop_callback: Optional[Callable[[], None]] = None,
        scratch_that_callback: Optional[Callable[[], bool]] = None,
        delete_sentence_callback: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._inject = inject_text
        self._press_key = press_key
        self._stop_callback = stop_callback
        self._scratch_that_callback = scratch_that_callback
        self._delete_sentence_callback = delete_sentence_callback

    def execute(self, tool: str) -> bool:
        """Execute the system action for the given tool name.

        Args:
            tool: Tool name from IntentResult (e.g. "NEW_LINE", "SAVE")

        Returns:
            True if the action was dispatched successfully
        """
        entry = self._TOOL_MAP.get(tool.upper())
        if entry is None:
            logger.warning("Unknown tool name: %r — ignoring", tool)
            return False

        action_type, value = entry
        logger.debug("Executing command: %s (%s %r)", tool, action_type, value)

        if action_type == "text":
            return self._inject(value)

        if action_type == "key":
            # Support compound sequences separated by ", "
            for combo in value.split(", "):
                self._press_key(combo.strip())
            return True

        if action_type == "special":
            return self._handle_special(value)

        return False

    def _handle_special(self, value: str) -> bool:
        if value == "STOP":
            if self._stop_callback:
                self._stop_callback()
            return True

        if value == "SCRATCH_THAT":
            if self._scratch_that_callback:
                return self._scratch_that_callback()
            # Fallback: single Ctrl+Z if no segment tracker available
            self._press_key("ctrl+z")
            return True

        if value == "DELETE_SENTENCE":
            if self._delete_sentence_callback:
                return self._delete_sentence_callback()
            # Fallback: three Ctrl+Z if no sentence tracker available
            for _ in range(3):
                self._press_key("ctrl+z")
            return True

        if value == "CAPITALIZE":
            # Select previous word and capitalize: Ctrl+Shift+Left, then retype
            # Simple approach: press Shift+Home, read not feasible without clipboard;
            # fallback to keyboard shortcut Shift+F3 (works in most text editors)
            self._press_key("shift+f3")
            return True

        if value == "LOWERCASE":
            self._press_key("shift+f3")
            self._press_key("shift+f3")
            return True

        logger.warning("Unhandled special command: %r", value)
        return False

    @classmethod
    def available_tools(cls) -> list[str]:
        """Return list of all supported tool names."""
        return list(cls._TOOL_MAP.keys())
