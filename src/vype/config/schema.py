"""Configuration schema using Pydantic for validation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class STTConfig(BaseModel):
    """NVIDIA Canary STT engine configuration."""

    model: str = "nvidia/canary-qwen-2.5b"  # any HuggingFace model ID
    device: str = "cuda"
    language: str = "en"
    max_new_tokens: int = 256           # ceiling for generation; auto-scaled per segment
    enable_pnc: bool = True             # Punctuation and Capitalization via SALM prompt
    context_tail_chars: int = 400       # characters of prior typed text passed as context


class VADConfig(BaseModel):
    """Silero Voice Activity Detection configuration."""

    enabled: bool = True
    method: str = "silero"
    threshold: float = 0.4
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 800
    max_segment_sec: float = 10.0
    window_size_samples: int = 512
    energy_threshold: float = 0.015


class AudioConfig(BaseModel):
    """Audio capture configuration."""

    device_id: int | None = None        # None = system default
    sample_rate: int = 16000            # Canary requires 16 kHz
    channels: int = 1                   # mono
    chunk_duration: float = 0.1         # seconds per sounddevice callback


class UIConfig(BaseModel):
    """User interface configuration."""

    show_visualizer: bool = True
    visualizer_size: int = 70
    visualizer_opacity: float = Field(0.9, ge=0.0, le=1.0)
    visualizer_position: tuple[int, int] = (100, 100)

    start_minimized: bool = True
    close_to_tray: bool = True
    hotkey: str = "ctrl+shift+space"

    accent_color_idle: str = "#3b82f6"
    accent_color_recording: str = "#ef4444"
    accent_color_processing: str = "#eab308"
    settings_window_opacity: float = Field(0.97, ge=0.7, le=1.0)
    overlay_opacity: float = Field(0.9, ge=0.5, le=1.0)


class OutputConfig(BaseModel):
    """Text output configuration."""

    primary_method: str = "keyboard"
    fallback_methods: list[str] = ["clipboard"]
    typing_speed: float = 0.01
    prefer_clipboard_over_chars: int = 200


class StreamingConfig(BaseModel):
    """Audio segmentation configuration."""

    min_segment_sec: float = 0.5
    energy_threshold: float = 0.015


class AppConfig(BaseModel):
    """Root application configuration."""

    stt: STTConfig = Field(default_factory=STTConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)

    log_level: str = "INFO"
    log_file: Path | None = None

    class Config:
        use_enum_values = True
