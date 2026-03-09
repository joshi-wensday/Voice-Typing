"""Intent Router — V2.1: command classification only.

The LLM is NEVER used to rewrite or clean transcription text.
It is only consulted when a short utterance is ambiguous between a voice
command and dictation — i.e. cases where regex alone is not enough.

Full-string regex handles the clear-cut commands (zero latency).
The LLM handles edge cases like "go back a bit", "actually undo that",
"can you save please" that don't match explicit patterns.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# Command-only system prompt — the LLM never sees a rewrite request.
COMMAND_SYSTEM_PROMPT = """\
You are a voice command classifier for a dictation app. The user may have spoken \
a system command or may be dictating text.

Classify the input as COMMAND or TRANSCRIPT.

COMMAND examples: "new line", "save the file", "delete that", "undo", \
"bullet point", "stop listening", "scratch that", "go back", "undo the last bit"

TRANSCRIPT examples: anything that reads like content being written — \
sentences, thoughts, descriptions, questions.

If COMMAND, identify the closest tool from:
DELETE_WORD, DELETE_LINE, DELETE_SENTENCE, NEW_LINE, NEW_PARAGRAPH, SAVE, UNDO, SCRATCH_THAT, BULLET_POINT, STOP

Rules:
- When in doubt, choose TRANSCRIPT — it is always safer to type than to act.
- Return ONLY valid JSON. No explanation.

Response: {"intent": "COMMAND|TRANSCRIPT", "tool": "TOOL_NAME or null"}\
"""

# Keywords that, when present in a short utterance, warrant an LLM check.
# This is a broad net — false positives are fine here; the LLM sorts them out.
_COMMAND_HINT_WORDS = re.compile(
    r"\b(new line|newline|new paragraph|save|delete|undo|scratch|scrap|cancel|"
    r"stop|bullet|go back|remove|clear|backspace|paragraph|revert|erase|wipe)\b",
    re.IGNORECASE,
)

# Maximum word count for an utterance to be considered a possible command.
# Anything longer than this is almost certainly dictation, not a command.
_MAX_COMMAND_WORDS = 8


class Intent(str, Enum):
    TRANSCRIPT = "TRANSCRIPT"
    COMMAND = "COMMAND"
    # REFACTOR kept for schema compatibility but not used on hot path in V2.1
    REFACTOR = "REFACTOR"


TOOL_DESCRIPTIONS: dict[str, str] = {
    "DELETE_WORD": "Delete last word",
    "DELETE_LINE": "Delete current line",
    "NEW_LINE": "Insert newline",
    "NEW_PARAGRAPH": "Insert double newline",
    "SAVE": "Save file (Ctrl+S)",
    "UNDO": "Undo last action (Ctrl+Z)",
    "DELETE_SENTENCE": "Delete last complete sentence",
    "SCRATCH_THAT": "Delete last dictated segment entirely",
    "BULLET_POINT": "Insert bullet point",
    "STOP": "Stop dictation",
    "CAPITALIZE": "Capitalize last word",
    "LOWERCASE": "Lowercase last word",
}


@dataclass
class IntentResult:
    intent: Intent
    tool: Optional[str] = None
    text: str = ""      # always the original text — LLM does not rewrite
    raw_text: str = ""

    @property
    def is_command(self) -> bool:
        return self.intent == Intent.COMMAND

    @property
    def is_refactor(self) -> bool:
        return self.intent == Intent.REFACTOR

    @property
    def is_transcript(self) -> bool:
        return self.intent == Intent.TRANSCRIPT

    def output_text(self) -> str:
        return self.raw_text or self.text


# Backward-compat alias
IntentAndTextResult = IntentResult


def is_likely_command(text: str) -> bool:
    """Heuristic gate: True only for short utterances that contain command keywords.

    When this returns False the LLM is never called — the text goes straight
    to the keyboard. This keeps the hot path at zero LLM latency for all normal
    dictation.

    Args:
        text: Raw Whisper transcription output

    Returns:
        True if the text is short enough and has a command keyword to warrant
        an LLM classification call.
    """
    words = text.split()
    if len(words) > _MAX_COMMAND_WORDS:
        return False
    return bool(_COMMAND_HINT_WORDS.search(text))


class IntentRouter:
    """Command-only LLM classifier.

    Only call `classify_command()` after `is_likely_command()` returns True.
    The LLM response is used purely for COMMAND/TRANSCRIPT classification and
    tool mapping — it never modifies the text.
    """

    def __init__(self, client: OllamaClient, model: str = "llama3.2") -> None:
        self._client = client
        self._model = model

    def classify_command(self, text: str) -> IntentResult:
        """Ask the LLM whether this short utterance is a command or dictation.

        The LLM only classifies — it does NOT rewrite or clean the text.
        Falls back to TRANSCRIPT on any failure so nothing is ever lost.

        Args:
            text: Short utterance from Whisper (already gated by is_likely_command)

        Returns:
            IntentResult — if COMMAND, result.tool contains the action to execute.
                           If TRANSCRIPT, caller should type the original text.
        """
        response = self._client.generate(
            model=self._model,
            prompt=text,
            system=COMMAND_SYSTEM_PROMPT,
            format="json",
        )

        if response:
            result = self._parse(response, text)
            if result is not None:
                logger.debug("LLM command check: %s (tool=%s) for %r", result.intent, result.tool, text)
                return result

        # On any failure, treat as TRANSCRIPT — safer than incorrectly executing a command
        logger.debug("LLM command check failed for %r — treating as TRANSCRIPT", text)
        return IntentResult(intent=Intent.TRANSCRIPT, text=text, raw_text=text)

    # V2.0 compatibility — some tests/callers may use classify_and_refine
    def classify_and_refine(self, text: str) -> IntentResult:
        """Compatibility shim — in V2.1 this no longer rewrites text."""
        if is_likely_command(text):
            return self.classify_command(text)
        return IntentResult(intent=Intent.TRANSCRIPT, text=text, raw_text=text)

    def classify(self, text: str) -> IntentResult:
        return self.classify_and_refine(text)

    def _parse(self, response: str, raw_text: str) -> Optional[IntentResult]:
        try:
            clean = re.sub(r"```(?:json)?|```", "", response).strip()
            data = json.loads(clean)
            intent_str = str(data.get("intent", "TRANSCRIPT")).upper()
            # Only accept COMMAND or TRANSCRIPT — ignore REFACTOR from LLM
            intent = Intent.COMMAND if intent_str == "COMMAND" else Intent.TRANSCRIPT
            tool = data.get("tool") or None
            if tool and tool not in TOOL_DESCRIPTIONS:
                tool = None
            # Text is always the original — never the LLM output
            return IntentResult(intent=intent, tool=tool, text=raw_text, raw_text=raw_text)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.debug("LLM response parse failed: %s", exc)
            return None

    def _local_fallback(self, text: str) -> IntentResult:
        """Compatibility shim used by old controller code."""
        return IntentResult(intent=Intent.TRANSCRIPT, text=text, raw_text=text)
