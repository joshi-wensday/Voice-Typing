"""Append-only JSONL transcript history — a journal dump is never lost."""

from __future__ import annotations

import json
import time
from pathlib import Path


class History:
    def __init__(self, path: Path, max_bytes: int = 10_000_000) -> None:
        self._path = Path(path)
        self._max_bytes = max_bytes

    def append(self, raw: str, cleaned: str | None = None) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists() and self._path.stat().st_size > self._max_bytes:
            rotated = self._path.with_name(f"{self._path.stem}.1{self._path.suffix}")
            rotated.unlink(missing_ok=True)
            self._path.rename(rotated)
        record = {"ts": time.time(), "raw": raw, "cleaned": cleaned}
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def last(self) -> dict | None:
        if not self._path.exists():
            return None
        last_line = None
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line
        return json.loads(last_line) if last_line else None

    def recent(self, n: int = 10) -> list[dict]:
        """Most recent records, newest first (for the pill's history popup)."""
        if not self._path.exists():
            return []
        with self._path.open("r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        return [json.loads(line) for line in reversed(lines[-n:])]

    def delete(self, ts: float) -> bool:
        """Remove the record with the given timestamp. Returns True if found."""
        if not self._path.exists():
            return False
        with self._path.open("r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        kept = [r for r in records if r.get("ts") != ts]
        if len(kept) == len(records):
            return False
        with self._path.open("w", encoding="utf-8") as f:
            for record in kept:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True

    def clear(self) -> None:
        """Privacy-first: wipe all stored transcripts (called at session end)."""
        self._path.unlink(missing_ok=True)
        rotated = self._path.with_name(f"{self._path.stem}.1{self._path.suffix}")
        rotated.unlink(missing_ok=True)

    def last_text(self) -> str | None:
        record = self.last()
        if record is None:
            return None
        return record["cleaned"] or record["raw"]
