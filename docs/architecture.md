# Architecture Overview

Voice Typing uses a modular architecture that separates concerns and enables extensibility. Each component has well-defined interfaces, making it easy to swap implementations, test in isolation, and extend functionality.

## Design Principles

1. **Modularity**: Components communicate through interfaces, not concrete implementations
2. **Configurability**: All behavior is controlled via configuration files
3. **Testability**: Each module can be tested independently
4. **Extensibility**: New STT engines, commands, and output methods can be added easily
5. **Local-First**: All processing happens on-device, no cloud dependencies

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Controller                          │
│                  (VoiceTypingController)                     │
│                                                              │
│  Orchestrates: Audio → STT → Command Processing → Output    │
└───────┬──────────────┬─────────────┬──────────┬─────────────┘
        │              │             │          │
┌───────▼──────┐  ┌────▼────────┐  ┌▼──────────▼──┐  ┌────────▼────┐
│    Audio     │  │     STT     │  │   Command    │  │   Output    │
│   Capture    │──│   Engine    │──│  Processor   │──│   Handler   │
│              │  │             │  │              │  │             │
└──────────────┘  └─────────────┘  └──────────────┘  └─────────────┘
                                                              │
┌──────────────────────────────────────────────────────────────▼─────┐
│                          UI Layer                                   │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────────┐ │
│  │  Hotkey  │  │   Tray   │  │  Overlay   │  │    Settings     │ │
│  │ Manager  │  │   Icon   │  │ Visualizer │  │     Window      │ │
│  └──────────┘  └──────────┘  └────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │   Config        │
                          │   Manager       │
                          │  (Pydantic)     │
                          └─────────────────┘
```

## Core Components

### 1. Audio Capture (`src/voice_typing/audio/capture.py`)

**Responsibility**: Capture audio from microphone in real-time.

**Key Features**:
- Device selection and enumeration
- Streaming buffer management
- Level monitoring for visualizer
- Configurable sample rate and channels

**Interface**:
```python
class AudioCapture:
    def start_recording() -> None
    def stop_recording() -> np.ndarray
    def drain_buffer() -> np.ndarray  # For streaming
    def list_devices() -> list[dict]
    def get_level() -> float  # For visualizer
```

**Dependencies**:
- `sounddevice` library for cross-platform audio
- `numpy` for buffer management

**Configuration** (`audio` section):
- `device_id`: Which microphone to use
- `sample_rate`: 16000 Hz (Whisper requirement)
- `channels`: 1 (mono)
- `chunk_duration`: Size of audio chunks

### 2. STT Engine (`src/voice_typing/stt/whisper_engine.py`)

**Responsibility**: Convert audio to text using Whisper.

**Key Features**:
- Model loading with CUDA/CPU fallback
- Batch and streaming transcription
- Context-aware transcription (uses previous text)
- Automatic compute type selection

**Interface**:
```python
class FasterWhisperEngine:
    def transcribe(audio: np.ndarray, sample_rate: int) -> TranscriptionResult
    def transcribe_incremental(audio: np.ndarray, initial_prompt: str) -> str
    def preload() -> None  # Warm-start model
    def load_model(model_name: str) -> None
    def get_supported_models() -> list[str]
```

**Dependencies**:
- `faster-whisper` (CTranslate2-optimized Whisper)
- `torch` (for CUDA acceleration)

**Configuration** (`stt` section):
- `model`: tiny/base/small/medium/large-v2/large-v3
- `device`: auto/cuda/cpu
- `compute_type`: float16/float32/int8
- `language`: "en" (or other ISO 639-1 codes)

**Swappability**: To add a different STT engine (Vosk, Coqui), create a new class implementing the same interface and register in a factory.

### 3. Command Processor (`src/voice_typing/commands/processor.py`)

**Responsibility**: Extract voice commands from transcribed text.

**Key Features**:
- Regex-based pattern matching
- Configurable punctuation modes (auto/manual/hybrid)
- Custom command registration
- Enable/disable individual commands

**Interface**:
```python
class CommandProcessor:
    def process(text: str) -> tuple[str, list[Command]]
```

**Command Types** (`src/voice_typing/commands/definitions.py`):
- `NewLineCommand`: Insert line break
- `PunctuationCommand`: Insert punctuation mark
- `InsertTextCommand`: Insert arbitrary text

**Configuration** (`punctuation` and `commands` sections):
- Patterns: Regex to match voice commands
- Actions: What text/action to insert
- Enabled flags: Turn commands on/off

**Extensibility**: Add custom commands in `config.yaml`:
```yaml
commands:
  custom_commands:
    my_email:
      pattern: "\\b(insert email)\\b"
      action: "user@example.com"
```

### 4. Output Handler (`src/voice_typing/output/handler.py`)

**Responsibility**: Inject text into the active application.

**Key Features**:
- Multiple output strategies with fallback
- Application-specific method selection
- Character-by-character typing or clipboard paste

**Strategies** (`src/voice_typing/output/strategies/`):

1. **Keyboard Strategy** (`keyboard.py`):
   - Uses `keyboard` library to simulate typing
   - Fast, works in 90% of applications
   - May bypass some input validation

2. **UIA Strategy** (`uia.py`):
   - Uses UI Automation for modern apps
   - Better compatibility with Office, Windows apps
   - Slower but more reliable

3. **Clipboard Strategy** (`clipboard.py`):
   - Copies text and simulates Ctrl+V
   - Fastest for long text
   - Overwrites clipboard (temporary)

**Interface**:
```python
class OutputHandler:
    def inject_text(text: str) -> bool
    def press_key(key: str) -> bool
    def execute_command(command: Command) -> bool
```

**Configuration** (`output` section):
- `primary_method`: First strategy to try
- `fallback_methods`: Backup strategies
- `typing_speed`: Delay between keystrokes
- `prefer_clipboard_over_chars`: Use clipboard for long text

### 5. Main Controller (`src/voice_typing/controller.py`)

**Responsibility**: Orchestrate the entire dictation flow.

**Key Features**:
- Streaming segmentation (near-real-time transcription)
- Energy-based silence detection
- Context-aware transcription
- Duplicate prevention
- Status callbacks for UI updates

**Data Flow**:
```
1. start_dictation()
   ↓
2. Audio capture starts in background
   ↓
3. Streaming loop monitors audio energy
   ↓
4. On silence detected:
   a. Finalize segment (transcribe audio chunk)
   b. Process commands
   c. Inject text delta (only new text)
   ↓
5. Loop continues until stop_dictation()
   ↓
6. Final segment processed
```

**Streaming Segmentation**:
- Monitors audio energy in real-time
- Segments audio when silence detected
- Transcribes each segment independently
- Injects text incrementally for responsiveness

**Configuration** (`streaming` section):
- `min_segment_sec`: Minimum audio length to transcribe
- `min_silence_sec`: Silence duration to trigger segment
- `energy_threshold`: Silence detection sensitivity

### 6. UI Components

#### Hotkey Manager (`src/voice_typing/ui/hotkey.py`, `hotkey_win32.py`)

**Responsibility**: Register global hotkeys for toggle activation.

**Features**:
- Multiple backend support (keyboard library, Win32 API)
- Automatic fallback if primary fails
- Configurable key combinations

#### System Tray (`src/voice_typing/ui/tray.py`)

**Responsibility**: Background application presence indicator.

**Features**:
- Color-coded status (green=idle, red=recording, yellow=processing)
- Right-click menu (Toggle, Settings, Exit)
- Runs in separate thread

#### Overlay Visualizer (`src/voice_typing/ui/overlay.py`)

**Responsibility**: Real-time audio level visualization.

**Features**:
- Circular waveform display
- Draggable to any position
- Left-click to toggle mute
- Right-click for settings
- Updates at 20 FPS (50ms intervals)

#### Settings Window (`src/voice_typing/ui/settings_window.py`)

**Responsibility**: GUI for configuration editing.

**Features**:
- Tabbed interface (General, Audio, Streaming, Decoding)
- Device selection dropdowns
- Real-time config updates
- Validation and error messages

### 7. Configuration Manager (`src/voice_typing/config/`)

**Responsibility**: Load, validate, and save configuration.

**Features**:
- Pydantic-based schema validation
- Type-safe configuration access
- Default value handling
- YAML serialization

**Schema** (`config/schema.py`):
- Defines all configuration options with types
- Provides defaults
- Validates values (e.g., opacity must be 0.0-1.0)

**Manager** (`config/manager.py`):
```python
class ConfigManager:
    def load() -> AppConfig
    def save(config: AppConfig) -> None
    def update(**kwargs) -> None
    def add_custom_command(...) -> None
    def toggle_command(path: str, enabled: bool) -> None
```

## Threading Model

Voice Typing uses multiple threads for responsiveness:

```
┌──────────────────────────────────────────┐
│            Main Thread                    │
│  - Tkinter UI event loop                 │
│  - Overlay rendering                     │
│  - Settings window                       │
└────────────┬─────────────────────────────┘
             │
┌────────────▼─────────────────────────────┐
│         Tray Thread                      │
│  - pystray system tray icon              │
└──────────────────────────────────────────┘
             │
┌────────────▼─────────────────────────────┐
│       Hotkey Thread(s)                   │
│  - Global hotkey listener                │
│  - Triggers controller.toggle()          │
└────────────┬─────────────────────────────┘
             │
┌────────────▼─────────────────────────────┐
│     Streaming Thread                     │
│  - Audio capture loop                    │
│  - Energy monitoring                     │
│  - Segment finalization                  │
│  - STT transcription                     │
└──────────────────────────────────────────┘
```

**Thread Safety**: Shared state is minimal. Controller uses events and locks for coordination.

## Configuration-Driven Behavior

All behavior is controlled via `~/.voice-typing/config.yaml`:

```yaml
stt:
  model: base  # Swap models without code changes

output:
  primary_method: keyboard  # Change output strategy

punctuation:
  mode: hybrid  # Auto, manual, or hybrid

commands:
  custom_commands:
    # Add new commands at runtime
```

Changes to config require app restart (or use Settings UI for hot-reload where supported).

## Extensibility Points

### Adding a New STT Engine

1. Implement interface in `src/voice_typing/stt/your_engine.py`
2. Add to configuration schema (new enum value)
3. Register in factory pattern
4. Update documentation

### Adding a New Voice Command

1. **Via Config** (no code needed):
   ```yaml
   commands:
     custom_commands:
       my_command:
         pattern: "\\b(trigger phrase)\\b"
         action: "text to insert"
   ```

2. **Via Code** (for complex commands):
   - Create new Command class in `commands/definitions.py`
   - Register in `CommandProcessor`

### Adding a New Output Strategy

1. Implement interface in `output/strategies/your_strategy.py`:
   ```python
   class YourStrategy:
       def is_available() -> bool
       def inject_text(text: str) -> bool
       def press_key(key: str) -> bool
   ```

2. Register in `OutputHandler._build_strategies()`

3. Add to config schema

## Error Handling Strategy

1. **Graceful Degradation**: If GPU fails, fallback to CPU
2. **Fallback Chains**: If keyboard injection fails, try clipboard
3. **User Notifications**: Tray icon shows error states
4. **Logging**: All errors logged with context
5. **Recovery**: Application continues running after errors

## Performance Considerations

### Latency Optimization

**Target**: <3 seconds from "stop speaking" to "text appears"

**Optimizations**:
1. Model preloading on startup (eliminates cold-start delay)
2. GPU acceleration (4x faster than CPU)
3. Streaming segmentation (incremental results)
4. Clipboard for long text (avoids slow character-by-character typing)
5. Energy-based silence detection (no unnecessary processing)

### Memory Management

- Audio buffers cleared after transcription
- Models loaded once and reused
- Streaming prevents unbounded buffer growth

### CPU Usage

- Idle: <1% CPU (only hotkey listener active)
- Recording: ~5-10% CPU (audio capture + energy monitoring)
- Transcribing: 50-100% CPU or GPU (model inference)

## Testing Strategy

### Unit Tests (`tests/unit/`)

Each component tested in isolation:
- Mock dependencies
- Test edge cases
- Verify interface contracts

### Integration Tests (`tests/integration/`)

Test component interactions:
- Full pipeline: audio → STT → commands → output
- Configuration loading and validation
- Multiple dictation sessions

### Manual Testing

Critical paths tested manually:
- Hotkey activation across applications
- Text injection in Notepad, VS Code, Chrome, Word
- Settings UI changes persist
- Overlay dragging and positioning

## Future Architecture Enhancements

Planned improvements:

1. **Plugin System**: Load custom STT engines from external modules
2. **Streaming Mode**: Display partial results in real-time
3. **Multi-Language**: Language auto-detection and switching
4. **Voice Profiles**: User-specific model fine-tuning
5. **macOS/Linux**: Cross-platform support with platform-specific adapters

## File Structure

```
src/voice_typing/
├── __init__.py
├── __main__.py              # Entry point
├── controller.py            # Main orchestrator
├── audio/
│   ├── capture.py           # Microphone input
│   └── devices.py           # Device enumeration
├── stt/
│   └── whisper_engine.py    # Whisper implementation
├── commands/
│   ├── processor.py         # Command extraction
│   └── definitions.py       # Command types
├── output/
│   ├── handler.py           # Output orchestrator
│   └── strategies/          # Injection methods
│       ├── keyboard.py
│       ├── uia.py
│       └── clipboard.py
├── ui/
│   ├── tray.py              # System tray
│   ├── overlay.py           # Visualizer
│   ├── settings_window.py   # Settings GUI
│   ├── hotkey.py            # Hotkey (keyboard lib)
│   └── hotkey_win32.py      # Hotkey (Win32 API)
├── config/
│   ├── manager.py           # Config I/O
│   └── schema.py            # Pydantic models
└── utils/
    └── system.py            # OS utilities
```

## Dependencies

**Core Dependencies**:
- `faster-whisper`: STT engine
- `sounddevice`: Audio capture
- `numpy`: Audio processing
- `pydantic`: Configuration validation
- `PyYAML`: Configuration serialization
- `keyboard`: Hotkey registration and typing
- `pywinauto`: UI Automation
- `pyperclip`: Clipboard operations
- `pystray`: System tray icon
- `Pillow`: Icon rendering

**Development Dependencies**:
- `pytest`: Testing framework
- `black`: Code formatting
- `flake8`: Linting
- `mypy`: Type checking
- `pre-commit`: Git hooks

## Conclusion

Voice Typing's modular architecture provides:
- **Flexibility**: Swap components without breaking others
- **Testability**: Each module has clear boundaries
- **Extensibility**: Add new features via configuration or plugins
- **Maintainability**: Clean interfaces and separation of concerns

For implementation details, see source code comments and docstrings.
