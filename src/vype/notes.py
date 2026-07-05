"""Persistent notes inbox (mobile capture lands here). Never auto-wiped —
unlike dictation history, a captured note must survive until the user
deliberately processes it."""

from __future__ import annotations

import json
import time
from pathlib import Path


class NotesStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def add(self, text: str, source: str = "app", tags: list[str] | None = None) -> dict:
        record = {"ts": time.time(), "text": text, "source": source, "tags": tags or []}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def recent(self, limit: int = 50) -> list[dict]:
        if not self._path.exists():
            return []
        with self._path.open("r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        return [json.loads(line) for line in reversed(lines[-limit:])]
