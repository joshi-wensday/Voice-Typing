"""Refiner: LLM-powered grammar and disfluency cleaner.

Cleans raw STT output for professional grammar while preserving the speaker's
voice. Also handles REFACTOR intent by applying edit instructions to prior text.
"""

from __future__ import annotations

import logging
import re

from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)

_REFINE_SYSTEM_PROMPT = """\
You are a professional transcription editor. Your job is to clean speech-to-text \
output for grammar and readability while STRICTLY preserving the speaker's voice \
and meaning.

Rules:
- Remove verbal stumbles: "um", "uh", "er", "ah", "like", "you know", "I mean", \
"basically", "literally", "actually", "so yeah".
- Remove self-corrections and restarts: "actually scratch that", "wait no", \
"let me rephrase", "I mean to say".
- Fix obvious transcription errors (wrong homophones, missing punctuation).
- Do NOT add new content, opinions, or paraphrasing beyond what was said.
- Do NOT change the speaker's vocabulary or style.
- Return ONLY the cleaned text. No explanation, no quotes, no prefix.\
"""

_REFACTOR_SYSTEM_PROMPT = """\
You are a voice dictation assistant. The user just issued an edit instruction \
while dictating. Apply the instruction to the prior text.

Rules:
- Apply the edit described in the instruction as literally as possible.
- Return ONLY the edited version of the prior text.
- If the instruction says "delete that" or "scratch that", return an empty string.
- Do NOT add commentary or explanation.\
"""

# Cheap local pre-filter for obvious fillers before sending to LLM
_LOCAL_FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|er+|ah+|ehh?|mm+|hmm+|like,?\s|you know,?\s|i mean,?\s"
    r"|basically,?\s|actually scratch that|wait no,?\s|let me rephrase)\b",
    re.IGNORECASE,
)


class Refiner:
    """Cleans transcription text using an Ollama LLM."""

    def __init__(self, client: OllamaClient, model: str = "llama3.2") -> None:
        self._client = client
        self._model = model

    def refine(self, text: str) -> str:
        """Clean a raw TRANSCRIPT segment.

        Applies local filler removal first, then sends to LLM for full
        grammatical refinement. Falls back to the locally-cleaned text
        if Ollama is unavailable.

        Args:
            text: Raw Whisper transcription output

        Returns:
            Cleaned text suitable for typing
        """
        if not text.strip():
            return text

        # Local pre-pass: strip obvious fillers cheaply
        pre_cleaned = re.sub(_LOCAL_FILLER_PATTERN, "", text)
        pre_cleaned = re.sub(r"\s{2,}", " ", pre_cleaned).strip()

        response = self._client.generate(
            model=self._model,
            prompt=pre_cleaned,
            system=_REFINE_SYSTEM_PROMPT,
        )

        if response:
            return response.strip()

        # LLM unavailable — return local pre-cleaned text
        logger.debug("Refiner LLM unavailable; using local pre-clean result")
        return pre_cleaned

    def apply_refactor(self, prior_text: str, instruction: str) -> str:
        """Apply a REFACTOR voice command to previously typed text.

        Args:
            prior_text: The text that was previously typed
            instruction: The refactor instruction from the user (e.g. "delete the last sentence")

        Returns:
            The modified text, or empty string if instruction deletes everything
        """
        if not prior_text.strip():
            return ""

        prompt = (
            f"Prior text:\n{prior_text}\n\n"
            f"Edit instruction: {instruction}"
        )

        response = self._client.generate(
            model=self._model,
            prompt=prompt,
            system=_REFACTOR_SYSTEM_PROMPT,
        )

        if response is not None and response != "":
            return response.strip()

        # Fallback: if we can't apply the refactor, return prior text unchanged
        logger.debug("Refactor LLM call failed; returning prior text unchanged")
        return prior_text
