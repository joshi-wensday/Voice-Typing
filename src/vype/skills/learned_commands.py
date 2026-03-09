"""Learned command store — persists user-specific voice command patterns.

When the user corrects a command via voice or UI feedback, the mapping is
saved here and checked on every segment before the LLM gate. This means
corrections take effect immediately on the next utterance with zero latency.

Storage: ~/.voice-typing/learned_commands.json
Format:  {"patterns": [{"phrase": "...", "tool": "NEW_LINE", "count": 3}]}
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".voice-typing" / "learned_commands.json"

# Characters to strip when normalizing phrases for comparison
_STRIP_PUNCT = re.compile(r"[^\w\s]")


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy matching."""
    text = text.lower().strip()
    text = _STRIP_PUNCT.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class LearnedCommandStore:
    """Persistent store mapping user phrase variants to command tool names.

    Thread safety: reads are frequent (every segment); writes are rare (feedback
    corrections). The simple approach of loading once and saving on every write
    is fine for this usage pattern.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._patterns: list[dict] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, text: str) -> Optional[str]:
        """Return the tool name for text if a learned pattern matches, else None.

        Matching is normalized (case-insensitive, punctuation-stripped,
        whitespace-collapsed) so minor transcription variations still match.
        """
        norm = _normalize(text)
        for entry in self._patterns:
            if _normalize(entry["phrase"]) == norm:
                return entry["tool"]
        return None

    def add(self, phrase: str, tool: str) -> None:
        """Add or update a phrase → tool mapping and persist immediately.

        If the phrase already exists (normalized match) its tool is updated and
        its count incremented. Otherwise a new entry is appended.
        """
        phrase = phrase.strip()
        norm_key = _normalize(phrase)
        for entry in self._patterns:
            if _normalize(entry["phrase"]) == norm_key:
                entry["tool"] = tool
                entry["count"] = entry.get("count", 0) + 1
                logger.info("Learned (updated): %r -> %s (count=%d)", phrase, tool, entry["count"])
                self._save()
                return
        self._patterns.append({"phrase": phrase, "tool": tool, "count": 1})
        logger.info("Learned (new): %r -> %s", phrase, tool)
        self._save()

    def remove(self, phrase: str) -> None:
        """Remove a learned pattern by phrase (normalized match)."""
        norm_key = _normalize(phrase)
        before = len(self._patterns)
        self._patterns = [e for e in self._patterns if _normalize(e["phrase"]) != norm_key]
        if len(self._patterns) < before:
            logger.info("Learned (removed): %r", phrase)
            self._save()

    def all_patterns(self) -> list[dict]:
        """Return a copy of all stored patterns."""
        return list(self._patterns)

    def __len__(self) -> int:
        return len(self._patterns)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._patterns = data.get("patterns", [])
            logger.debug("Loaded %d learned command patterns from %s", len(self._patterns), self._path)
        except Exception as exc:
            logger.warning("Failed to load learned commands from %s: %s", self._path, exc)
            self._patterns = []

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({"patterns": self._patterns}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save learned commands to %s: %s", self._path, exc)
