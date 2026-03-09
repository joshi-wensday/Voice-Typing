"""Synchronous Ollama HTTP client for local LLM inference.

Communicates with an Ollama server at localhost:11434 using the /api/generate
endpoint with streaming disabled for predictable latency.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class OllamaClient:
    """Thin synchronous wrapper around the Ollama REST API."""

    def __init__(self, endpoint: str = "http://localhost:11434", timeout: float = 5.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def warmup(self, model: str) -> bool:
        """Pre-load the model into VRAM so the first real request is instant.

        Sends a minimal generation request with keep_alive=-1 so the model
        stays resident in VRAM until Ollama is stopped. Uses an extended
        timeout (60s) to accommodate cold-start model loading from disk.

        Returns:
            True if the model loaded successfully, False on error.
        """
        logger.info("Warming up Ollama model '%s' (loading into VRAM)...", model)
        # Use a longer timeout for the warmup — model load from disk can take 20s+
        original_timeout = self.timeout
        self.timeout = 60.0
        try:
            response = self.generate(model=model, prompt=".", keep_alive=-1)
        finally:
            self.timeout = original_timeout
        if response is not None:
            logger.info("Ollama model '%s' warm and ready.", model)
            return True
        logger.warning("Ollama warmup failed for model '%s'.", model)
        return False

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        format: str | None = None,
        keep_alive: int | str = "30m",
    ) -> str:
        """Send a generation request and return the response text.

        Args:
            model: Ollama model name (e.g. "llama3.2")
            prompt: User prompt text
            system: Optional system prompt
            format: Optional response format ("json" to request structured output)
            keep_alive: How long to keep model in VRAM after this request.
                        -1 = indefinite, "5m" = 5 minutes (Ollama default).
                        Set to -1 after warmup so the model is never evicted.

        Returns:
            Model response text, or empty string on failure.
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
        }
        if system:
            payload["system"] = system
        if format:
            payload["format"] = format

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                result = json.loads(body)
                return result.get("response", "").strip()
        except urllib.error.URLError as exc:
            logger.warning("Ollama connection failed: %s", exc)
            return ""
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Ollama response parse error: %s", exc)
            return ""
        except TimeoutError:
            logger.warning("Ollama request timed out after %.1fs", self.timeout)
            return ""

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            with urllib.request.urlopen(f"{self.endpoint}/api/tags", timeout=2.0):
                return True
        except Exception:
            return False
