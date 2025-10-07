# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### To Do
- Multi-language support beyond English
- macOS and Linux support
- Plugin system for custom STT engines
- Advanced streaming mode with partial results
- Voice activity detection (VAD) improvements

## [0.1.0] - 2025-01-08

### Added
- Initial release of Voice Typing
- Local speech-to-text using OpenAI Whisper via faster-whisper
- Global hotkey activation with toggle mode (press to start/stop)
- Real-time circular audio visualizer overlay
  - Draggable to any screen position
  - Shows audio levels during recording
  - Right-click to open settings
- Voice commands support:
  - "new line" - Insert line break
  - "period", "comma", "question mark", "exclamation mark" - Insert punctuation
  - "stop dictation" - End recording session
- Configurable punctuation modes:
  - Auto: Use Whisper's built-in punctuation
  - Manual: Voice commands only
  - Hybrid: Both (manual overrides auto)
- Custom command support via configuration
- System tray integration
  - Visual status indicator (idle=green, recording=red, processing=yellow)
  - Quick access to toggle dictation
  - Settings menu access
- Comprehensive settings UI with tabs for:
  - General settings (model, device, hotkey)
  - Audio input device selection
  - Streaming/segmentation parameters
  - Decoding parameters (beam size, temperature)
- Multiple text output strategies:
  - Keyboard simulation (primary)
  - UI Automation (UIA)
  - Win32 API
  - Clipboard fallback
- Streaming segmentation for near-real-time dictation
  - Energy-based silence detection
  - Configurable segment length and silence thresholds
  - Context-aware transcription with initial prompts
- Support for multiple Whisper models:
  - tiny (39M params) - Fastest
  - base (74M params) - Recommended
  - small (244M params) - Better accuracy
  - medium (769M params) - High accuracy
  - large-v2/v3 (1550M params) - Best accuracy
- GPU acceleration with CUDA support
- Comprehensive YAML-based configuration
  - User config stored in `~/.voice-typing/config.yaml`
  - All settings configurable via file or UI
- Development tools:
  - Automated setup script (`scripts/setup_dev.py`)
  - Model download utility (`scripts/download_models.py`)
  - Pre-commit hooks for code quality
  - Comprehensive test suite
- Documentation:
  - Installation guide
  - Configuration reference
  - Architecture documentation
  - Development guide
  - Contribution guidelines
- CI/CD with GitHub Actions:
  - Automated testing on multiple Python versions
  - Code quality checks (flake8, mypy, black)
  - Automated release workflow

### Technical Details
- Python 3.10+ required
- Windows 10/11 support
- Modular architecture with clean interface contracts
- Type-annotated codebase with mypy verification
- 80%+ test coverage
- Follows PEP 8 style guidelines

### Known Limitations
- Windows only (macOS/Linux support planned)
- English language only (multi-language support planned)
- Requires administrator privileges for global hotkey registration
- Some applications may require clipboard fallback for text injection

### Performance
- <3 second transcription latency on GTX 1080 with base model
- ~1-2s latency with CUDA acceleration
- Minimal CPU/memory usage when idle