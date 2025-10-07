# Architecture Overview

Voice Typing is composed of modular components with clear interfaces.

## Components
- Audio Capture: records microphone input
- STT Engine: transcribes audio to text (Whisper via faster-whisper)
- Command Processor: extracts and handles voice commands
- Output Handler: injects text/commands into active applications
- UI: system tray and visualizer overlay
- Config: Pydantic-based configuration management

## Data Flow
1. User toggles hotkey
2. Audio capture records audio
3. STT engine transcribes to text
4. Command processor produces (clean_text, commands)
5. Output handler injects text and executes commands

## Swappability
Components are swappable via configuration and factory patterns. Configurable via `~/.voice-typing/config.yaml`.
