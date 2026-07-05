"""Configuration: pydantic schema + YAML persistence at ~/.vype/config.yaml."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "config.yaml"


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class HotkeyConfig(_Model):
    key: str = "ctrl+alt"  # single key ("f8") or combo ("ctrl+alt")
    tap_threshold_ms: int = 300


class SttConfig(_Model):
    backend: str = "parakeet"  # parakeet | whisper | openai
    device: str = "cuda"
    model: str | None = None  # backend-specific model override
    base_url: str | None = None  # openai backend only
    api_key: str | None = None


class CleanupConfig(_Model):
    enabled: bool = False
    base_url: str = "http://localhost:11434/v1"
    api_key: str | None = None
    model: str = "qwen3:8b"
    timeout_s: float = 5.0


class AudioConfig(_Model):
    device_id: int | None = None  # None = system default microphone
    sample_rate: int = 16000


class UiConfig(_Model):
    show_pill: bool = True
    live_preview: bool = True
    preview_at_caret: bool = True  # caption follows the text caret; False → above the pill
    preview_interval_s: float = 1.5
    # measured on RTX 3080: ~60 ms per second of audio, so 10 s ≈ 0.6 s per tick —
    # fits the 1.5 s cadence; 30 s would overrun it
    preview_window_s: float = 10.0


class Config(_Model):
    hotkey: HotkeyConfig = Field(default_factory=HotkeyConfig)
    stt: SttConfig = Field(default_factory=SttConfig)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    min_utterance_s: float = 0.3
    # trailing space after each paste so back-to-back utterances don't fuse
    append_space: bool = True


def config_dir() -> Path:
    override = os.environ.get("VYPE_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".vype"


def config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    if not path.exists():
        cfg = Config()
        save_config(cfg, path)
        return cfg
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"config root is {type(data).__name__}, expected mapping")
        return Config.model_validate(data)
    except Exception as exc:
        logger.warning("Could not parse %s (%s) — using defaults", path, exc)
        return Config()


def save_config(cfg: Config, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(cfg.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
