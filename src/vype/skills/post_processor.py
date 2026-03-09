"""Post-Processor Skill: handles grammar refinement and REFACTOR intent.

This skill is the V2 replacement for the disabled `improve_grammar` flag in
TextProcessor. It delegates to the Refiner brain module for LLM-based cleaning.
"""

from __future__ import annotations

import logging

from ..brain.intent_router import Intent, IntentResult
from ..brain.refiner import Refiner

logger = logging.getLogger(__name__)


class PostProcessorSkill:
    """Processes TRANSCRIPT and REFACTOR intents through the Refiner LLM.

    For TRANSCRIPT: cleans grammar and removes disfluencies.
    For REFACTOR: applies the user's edit instruction to accumulated prior text.
    """

    def __init__(self, refiner: Refiner) -> None:
        self._refiner = refiner
        # Tracks the last N characters of typed text for REFACTOR operations
        self._typed_buffer: str = ""
        self._buffer_max_chars: int = 2000

    def process_transcript(self, text: str) -> str:
        """Clean a TRANSCRIPT segment and update the typed buffer.

        Args:
            text: Raw Whisper output classified as TRANSCRIPT

        Returns:
            Cleaned text ready for typing
        """
        cleaned = self._refiner.refine(text)
        self._append_to_buffer(cleaned)
        return cleaned

    def process_refactor(self, instruction: str) -> tuple[str, int]:
        """Apply a REFACTOR instruction against the typed buffer.

        Args:
            instruction: The raw voice refactor instruction (e.g. "delete the last sentence")

        Returns:
            Tuple of (replacement_text, chars_to_delete) where chars_to_delete
            is the number of characters to backspace before typing replacement_text.
            If the refactor deletes everything in the buffer, replacement_text is "".
        """
        if not self._typed_buffer:
            logger.debug("Refactor called but typed buffer is empty")
            return ("", 0)

        original = self._typed_buffer
        modified = self._refiner.apply_refactor(original, instruction)

        # Calculate the diff: how many chars were removed from the tail
        chars_to_delete = len(original) - _common_prefix_len(original, modified)
        replacement = modified[_common_prefix_len(original, modified):]

        # Update buffer to reflect the refactored state
        self._typed_buffer = modified[-self._buffer_max_chars :]

        logger.debug(
            "Refactor applied: deleted %d chars, inserted %d chars",
            chars_to_delete,
            len(replacement),
        )
        return (replacement, chars_to_delete)

    def reset_buffer(self) -> None:
        """Clear the typed buffer at the start of a new dictation session."""
        self._typed_buffer = ""

    def _append_to_buffer(self, text: str) -> None:
        self._typed_buffer += text
        if len(self._typed_buffer) > self._buffer_max_chars:
            self._typed_buffer = self._typed_buffer[-self._buffer_max_chars :]


def _common_prefix_len(a: str, b: str) -> int:
    """Return the length of the common prefix of two strings."""
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i
