"""Configuration schema using Pydantic for validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class STTModel(str, Enum):
    """Available Whisper models."""

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large-v2"


class Device(str, Enum):
    """Compute device for inference."""

    CUDA = "cuda"
    CPU = "cpu"
    AUTO = "auto"


class PunctuationMode(str, Enum):
    """Punctuation handling modes."""

    AUTO = "auto"  # Whisper's built-in only
    MANUAL = "manual"  # Voice commands only
    HYBRID = "hybrid"  # Both (manual overrides auto)


class CommandConfig(BaseModel):
    """Individual command configuration."""

    enabled: bool = True
    pattern: str
    action: str
    description: str = ""


class STTConfig(BaseModel):
    """Speech-to-text engine configuration."""

    model: STTModel = STTModel.BASE
    device: Device = Device.AUTO
    language: str = "en"
    compute_type: str = "float16"  # int8, float16, float32
    remove_filler_words: bool = False  # Remove um, uh, etc.
    improve_grammar: bool = False  # Context-aware grammar improvement


class AudioConfig(BaseModel):
    """Audio capture configuration."""

    device_id: int | None = None  # None = default device
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration: float = 0.5  # seconds
    vad_enabled: bool = False
    vad_aggressiveness: int = Field(2, ge=0, le=3)


def _default_punctuation_commands() -> dict[str, CommandConfig]:
    return {
        "period": CommandConfig(
            enabled=True,
            pattern=r"\b(period|full stop)\b",
            action=".",
            description="Insert period",
        ),
        "comma": CommandConfig(
            enabled=True,
            pattern=r"\b(comma)\b",
            action=",",
            description="Insert comma",
        ),
        "question_mark": CommandConfig(
            enabled=True,
            pattern=r"\b(question mark)\b",
            action="?",
            description="Insert question mark",
        ),
        "exclamation_mark": CommandConfig(
            enabled=True,
            pattern=r"\b(exclamation mark|exclamation point)\b",
            action="!",
            description="Insert exclamation mark",
        ),
    }


class PunctuationConfig(BaseModel):
    """Punctuation handling configuration."""

    mode: PunctuationMode = PunctuationMode.HYBRID
    auto_capitalize: bool = True

    # Manual command overrides
    manual_commands: dict[str, CommandConfig] = Field(default_factory=_default_punctuation_commands)


class CommandsConfig(BaseModel):
    """Voice commands configuration."""

    enabled: bool = True

    # Built-in control commands
    new_line: CommandConfig = CommandConfig(
        enabled=True, pattern=r"\b(new line|newline)\b", action="\\n", description="Insert line break"
    )
    stop_dictation: CommandConfig = CommandConfig(
        enabled=True,
        pattern=r"\b(stop dictation|stop listening)\b",
        action="STOP",
        description="End recording session",
    )

    # User-defined custom commands
    custom_commands: dict[str, CommandConfig] = Field(default_factory=dict)


class UIConfig(BaseModel):
    """User interface configuration."""

    # Visualizer overlay
    show_visualizer: bool = True
    visualizer_size: int = 70  # pixels (reduced for cleaner look)
    visualizer_opacity: float = Field(0.9, ge=0.0, le=1.0)  # Increased for better visibility
    visualizer_position: tuple[int, int] = (100, 100)  # x, y from top-left

    # System tray
    start_minimized: bool = True
    close_to_tray: bool = True

    # Hotkey
    hotkey: str = "ctrl+shift+space"
    
    # Appearance customization
    accent_color_idle: str = "#3b82f6"  # Blue
    accent_color_recording: str = "#ef4444"  # Red
    accent_color_processing: str = "#eab308"  # Yellow/Gold
    settings_window_opacity: float = Field(0.97, ge=0.7, le=1.0)
    overlay_opacity: float = Field(0.9, ge=0.5, le=1.0)


class OutputConfig(BaseModel):
    """Text output configuration."""

    primary_method: str = "keyboard"  # keyboard, uia, win32, clipboard
    fallback_methods: list[str] = ["clipboard"]
    typing_speed: float = 0.01  # delay between characters (seconds)
    prefer_clipboard_over_chars: int = 200


class StreamingConfig(BaseModel):
    """Streaming/segmentation configuration."""

    mode: str = "final_only"  # final_only | semi_streaming (future)
    segmentation: str = "energy"  # energy | vad (future)
    min_segment_sec: float = 1.2
    min_silence_sec: float = 0.6
    energy_threshold: float = 0.015


class DecodingConfig(BaseModel):
    """Decoding parameters for Whisper."""

    beam_size: int = 5
    temperature: float = 0.0
    condition_on_previous_text: bool = True


class AppConfig(BaseModel):
    """Root application configuration."""

    stt: STTConfig = Field(default_factory=STTConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    punctuation: PunctuationConfig = Field(default_factory=PunctuationConfig)
    commands: CommandsConfig = Field(default_factory=CommandsConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)
    decoding: DecodingConfig = Field(default_factory=DecodingConfig)

    # Logging
    log_level: str = "INFO"
    log_file: Path | None = None

    class Config:
        use_enum_values = True
