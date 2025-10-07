# Contributing to Voice Typing

Thank you for your interest in contributing! This document provides guidelines and setup instructions.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

### Development Environment

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/voice-typing.git
   cd voice-typing
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   pre-commit install
   ```

4. **Verify installation**
   ```bash
   pytest tests/
   ```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes with tests**
   - Write tests first (TDD encouraged)
   - Ensure all tests pass: `pytest tests/`
   - Check code quality: `pre-commit run --all-files`

3. **Commit with conventional commits**
   ```
   feat: add custom command registration
   fix: resolve audio buffer overflow
   docs: update installation instructions
   ```

4. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Standards

### Style Guide

- PEP 8 compliance (enforced by `black` and `flake8`)
- Type hints required for all functions
- Docstrings for all public APIs (Google style)

Example:

```python
def transcribe(self, audio_data: bytes) -> str:
    """Convert audio data to text.

    Args:
        audio_data: Raw audio bytes in 16kHz PCM format

    Returns:
        Transcribed text string

    Raises:
        TranscriptionError: If audio format is invalid

    Example:
        >>> engine = WhisperEngine()
        >>> text = engine.transcribe(audio_bytes)
        >>> print(text)
        "Hello world"
    """
    pass
```

### Testing Requirements

- Unit tests for all new functions
- Integration tests for module interactions
- Minimum 80% coverage for new code

Run tests:

```bash
# All tests
pytest tests/

# With coverage report
pytest tests/ --cov=voice_typing --cov-report=html

# Specific test file
pytest tests/unit/test_stt_engine.py
```

### Architecture Guidelines

- Follow interface contracts defined in `base.py` files
- Keep modules loosely coupled
- Use dependency injection where appropriate
- Document design decisions in code comments

## Areas for Contribution

### High Priority

- macOS support (audio capture, text injection)
- Linux support (X11/Wayland compatibility)
- Performance optimizations (model quantization)
- Additional STT engine adapters (Vosk, Coqui)

### Good First Issues

- Add more voice commands (see `commands/builtin.py`)
- Improve error messages
- Write documentation examples
- Create test audio fixtures

### Advanced

- Streaming transcription mode
- Plugin system architecture
- Multi-language support
- Voice profile training

See [Issues](https://github.com/yourusername/voice-typing/issues) for full list.

## Pull Request Process

1. Update documentation if adding features
2. Add tests for bug fixes and new code
3. Update `CHANGELOG.md` under "Unreleased" section
4. Ensure CI passes (tests, linting, type checks)
5. Request review from maintainers

### PR Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Type hints added
- [ ] Pre-commit hooks pass
- [ ] No breaking changes (or documented in PR)

## Adding a Custom STT Engine

To add support for a new STT engine (e.g., Vosk, Coqui):

### 1. Implement the Interface

```python
# src/voice_typing/stt/vosk_engine.py
from .base import STTEngineInterface

class VoskEngine(STTEngineInterface):
    def __init__(self, model_path: str):
        self.model = vosk.Model(model_path)

    def transcribe(self, audio_data: bytes) -> str:
        # Implementation
        pass

    def load_model(self, model_name: str) -> None:
        # Implementation
        pass

    def get_supported_models(self) -> list[str]:
        return ["vosk-model-small-en-us-0.15"]
```

### 2. Register in Factory

```python
# src/voice_typing/stt/__init__.py
from .whisper_engine import FasterWhisperEngine
from .vosk_engine import VoskEngine

ENGINE_REGISTRY = {
    "faster_whisper": FasterWhisperEngine,
    "vosk": VoskEngine,
}

def create_engine(engine_type: str, **kwargs) -> STTEngineInterface:
    engine_class = ENGINE_REGISTRY.get(engine_type)
    if not engine_class:
        raise ValueError(f"Unknown engine: {engine_type}")
    return engine_class(**kwargs)
```

### 3. Add Tests

```python
# tests/unit/test_vosk_engine.py
def test_vosk_transcription():
    engine = VoskEngine(model_path="path/to/model")
    audio = load_test_audio()
    text = engine.transcribe(audio)
    assert len(text) > 0
```

### 4. Update Documentation

Add to `docs/configuration.md`.

## Questions?

- 📖 Check the [Documentation](docs/)
- 🐛 Open an [Issue](https://github.com/yourusername/voice-typing/issues)
- 💬 Start a [Discussion](https://github.com/yourusername/voice-typing/discussions)

Thank you for making Voice Typing better! 🎉
