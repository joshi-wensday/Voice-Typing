"""Context Summarizer: maintains a rolling keyword summary for Whisper lexical biasing.

Keeps a 2-minute rolling window of transcribed text and uses an Ollama LLM to
distill it into ~50 keywords that are injected as Whisper's `initial_prompt`.
This biases the acoustic model toward current topics, names, and jargon.

Keyword refreshes are done on a daemon background thread so they never block
the audio pipeline. The previous keyword string is reused while the refresh runs.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a keyword extractor for a speech recognition system. Given the following \
transcript, output EXACTLY 50 comma-separated keywords and proper nouns that \
should bias the speech model toward the current topic. Focus on: names, technical \
terms, jargon, acronyms, and topic-specific vocabulary. No sentences, no \
explanation, no numbering. Just a flat comma-separated list.\
"""


@dataclass
class _TranscriptSegment:
    text: str
    timestamp: float = field(default_factory=time.monotonic)


class ContextSummarizer:
    """Maintains a rolling transcript window and exposes a keyword prompt.

    The keyword summary is refreshed asynchronously (every N new segments)
    to avoid adding LLM latency to the hot path. Between refreshes the last
    known keyword string is reused.
    """

    def __init__(
        self,
        client: OllamaClient,
        model: str = "llama3.2",
        window_sec: float = 120.0,
        refresh_every: int = 3,
        max_keywords: int = 50,
    ) -> None:
        self._client = client
        self._model = model
        self._window_sec = window_sec
        self._refresh_every = refresh_every
        self._max_keywords = max_keywords

        self._segments: Deque[_TranscriptSegment] = deque()
        self._keyword_prompt: str = ""
        self._segments_since_refresh: int = 0
        self._refresh_lock = threading.Lock()
        self._refresh_in_progress: bool = False

    def add_segment(self, text: str) -> None:
        """Add a new transcription segment to the rolling window.

        Triggers a non-blocking keyword refresh on a background thread when
        enough new segments have accumulated. The caller is never blocked.

        Args:
            text: Transcribed text from Whisper
        """
        if not text.strip():
            return
        self._segments.append(_TranscriptSegment(text=text.strip()))
        self._evict_old()
        self._segments_since_refresh += 1

        if self._segments_since_refresh >= self._refresh_every and not self._refresh_in_progress:
            self._segments_since_refresh = 0
            t = threading.Thread(target=self._refresh_keywords_bg, daemon=True)
            t.start()

    def get_prompt(self) -> str:
        """Return the current keyword prompt string for Whisper's initial_prompt.

        Falls back to a raw transcript tail if no LLM summary is available.
        """
        if self._keyword_prompt:
            return self._keyword_prompt
        # Fallback: last 200 chars of raw transcript
        return self._raw_tail(200)

    def reset(self) -> None:
        """Clear all context (call at start of a new dictation session)."""
        self._segments.clear()
        self._keyword_prompt = ""
        self._segments_since_refresh = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evict_old(self) -> None:
        """Remove segments outside the rolling window."""
        cutoff = time.monotonic() - self._window_sec
        while self._segments and self._segments[0].timestamp < cutoff:
            self._segments.popleft()

    def _raw_tail(self, max_chars: int) -> str:
        """Return the tail of the raw rolling transcript."""
        combined = " ".join(s.text for s in self._segments)
        return combined[-max_chars:].strip()

    def _refresh_keywords_bg(self) -> None:
        """Background-thread wrapper: sets in-progress flag, calls LLM, clears flag."""
        with self._refresh_lock:
            self._refresh_in_progress = True
        try:
            self._refresh_keywords()
        finally:
            with self._refresh_lock:
                self._refresh_in_progress = False

    def _refresh_keywords(self) -> None:
        """Call Ollama to regenerate the keyword summary (runs on background thread)."""
        transcript = self._raw_tail(1500)
        if not transcript:
            return

        response = self._client.generate(
            model=self._model,
            prompt=f"Transcript:\n{transcript}",
            system=SYSTEM_PROMPT,
        )
        if response:
            keywords = [kw.strip() for kw in response.split(",") if kw.strip()]
            self._keyword_prompt = ", ".join(keywords[: self._max_keywords])
            logger.debug("Context keywords refreshed: %d terms", len(keywords))
        else:
            logger.debug("Context summarizer returned empty; keeping previous prompt")
