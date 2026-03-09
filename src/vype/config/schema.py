"""Configuration schema using Pydantic for validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class STTModel(str, Enum):
    """Available speech-to-text model presets.

    Notes:
    - Most values here refer to faster-whisper models.
    - `canary-qwen-2.5b` uses NVIDIA NeMo (optional dependency) and ignores some
      Whisper-specific decoding knobs.
    """

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large-v2"
    LARGE_V3 = "large-v3"
    CANARY_QWEN_2_5B = "canary-qwen-2.5b"


class STTBackend(str, Enum):
    """STT backend implementation.

    - whisper: faster-whisper
    - nemo: NVIDIA NeMo (SpeechLM2 / SALM)
    """

    WHISPER = "whisper"
    NEMO = "nemo"


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

    backend: STTBackend = STTBackend.WHISPER
    model: STTModel = STTModel.LARGE_V3
    device: Device = Device.CUDA
    language: str = "en"
    compute_type: str = "float16"  # float16: max quality (~3.1GB VRAM, recommended for RTX 3080+); int8_float16: lower VRAM; int8: CPU
    remove_filler_words: bool = False  # handled by Refiner skill in V2
    improve_grammar: bool = False  # handled by Refiner skill in V2


class VADConfig(BaseModel):
    """Voice Activity Detection configuration."""

    enabled: bool = True
    method: str = "silero"  # silero | energy
    # Silero VAD thresholds
    threshold: float = Field(0.4, ge=0.0, le=1.0)
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 800
    max_segment_sec: float = 10.0
    window_size_samples: int = 512
    # Energy fallback threshold (used when method=energy)
    energy_threshold: float = 0.015


class AudioConfig(BaseModel):
    """Audio capture configuration."""

    device_id: int | None = None  # None = default device
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration: float = 0.1  # smaller chunks for lower VAD latency
    vad_enabled: bool = False  # legacy flag, superseded by VADConfig
    vad_aggressiveness: int = Field(2, ge=0, le=3)


class BrainConfig(BaseModel):
    """Ollama LLM brain configuration."""

    enabled: bool = True
    endpoint: str = "http://localhost:11434"
    model: str = "llama3.2"
    timeout_sec: float = 10.0
    # Context summarizer window
    context_window_sec: float = 120.0  # rolling 2-minute transcript window
    context_max_keywords: int = 50
    # Feature toggles
    intent_routing_enabled: bool = True
    refinement_enabled: bool = True
    context_summarizer_enabled: bool = True


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
    segmentation: str = "vad"  # vad | energy
    min_segment_sec: float = 0.5
    min_silence_sec: float = 0.4
    energy_threshold: float = 0.015  # fallback when segmentation=energy


class DecodingConfig(BaseModel):
    """Decoding parameters for Whisper."""

    beam_size: int = 5
    temperature: float = 0.0
    # Setting this to False is the primary fix for looping hallucinations; Whisper
    # will not condition each new segment on its own previously generated tokens.
    condition_on_previous_text: bool = False
    # Segments whose average log-probability is below this are discarded.
    # -1.0 accepts everything; -0.4 discards low-confidence segments.
    log_prob_threshold: float = -0.4
    # Segments with a gzip compression ratio above this are likely repetitive
    # hallucinations and are discarded.
    compression_ratio_threshold: float = 2.4
    # Segments where Whisper's internal no-speech probability exceeds this
    # threshold are discarded rather than transcribed.
    no_speech_threshold: float = 0.6
    # Beam search patience multiplier. 1.0 = stop as soon as beam_size finished
    # beams are found. 2.0 = explore twice as many candidates before committing,
    # improving accuracy at a modest compute cost.
    patience: float = 2.0
    # Penalises repeated tokens in the decoder output. Values slightly above 1.0
    # discourage Whisper's tendency to repeat n-grams when audio is ambiguous.
    repetition_penalty: float = 1.1


class AppConfig(BaseModel):
    """Root application configuration."""

    stt: STTConfig = Field(default_factory=STTConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
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
