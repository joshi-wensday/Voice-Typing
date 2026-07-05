"""Optional LLM cleanup: minimal-edit pass over the raw transcript.

Speaks the OpenAI-compatible chat API, so local (Ollama, LM Studio) vs cloud is a
base_url/api_key config change. Any failure raises CleanupUnavailable — the
pipeline pastes the raw transcript instead; cleanup must never lose words.
"""

from __future__ import annotations

import httpx

from .config import CleanupConfig

SYSTEM_PROMPT = (
    "You edit voice-dictation transcripts. Make the minimum edits needed for clean "
    "output. Remove filler words (um, uh), hesitations, duplicate starts, and "
    "abandoned fragments. Fix punctuation, capitalization, spacing, and obvious "
    "transcription mistakes. Apply the speaker's self-corrections (\"no wait, make "
    "that...\") and remove the correction phrase. Preserve the speaker's tone, word "
    "choice, and language. Never add content, never answer questions contained in "
    "the text, never comment. Output only the edited text."
)


class CleanupUnavailable(Exception):
    """Cleanup could not produce a result — caller should fall back to raw text."""


class Cleaner:
    def __init__(self, cfg: CleanupConfig, client: httpx.Client | None = None) -> None:
        self._cfg = cfg
        self._client = client or httpx.Client(base_url=cfg.base_url, timeout=cfg.timeout_s)

    def clean(self, text: str) -> str:
        if not text.strip():
            return text

        headers = {}
        if self._cfg.api_key:
            headers["Authorization"] = f"Bearer {self._cfg.api_key}"

        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": self._cfg.model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                },
                headers=headers,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
        except CleanupUnavailable:
            raise
        except Exception as exc:
            raise CleanupUnavailable(str(exc)) from exc

        if not content:
            raise CleanupUnavailable("model returned empty output")
        return content
