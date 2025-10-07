# Development Guide

This guide covers setting up your development environment and contributing to Voice Typing.

## Prerequisites
- Windows 10/11
- Python 3.10+
- Git
- NVIDIA GPU with CUDA (optional)

## Automated Setup (Recommended)
```bash
python scripts/setup_dev.py
```
This script will:
- Create a virtual environment
- Install dependencies (including dev tools)
- Install pre-commit hooks
- Download the default Whisper model

## Manual Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install -e .[dev]
pre-commit install
python scripts/download_models.py --model base
```

## Running Tests
```bash
pytest tests/
pytest tests/ --cov=voice_typing --cov-report=html
```

## Code Quality
- Formatting: black
- Linting: flake8
- Types: mypy

Run all hooks:
```bash
pre-commit run --all-files
```

## Project Structure
```
src/voice_typing/
  audio/         # Audio capture and device management
  stt/           # Speech-to-text engines
  commands/      # Voice command processing
  output/        # Text injection handlers
  ui/            # User interface components
  config/        # Configuration management
  utils/         # Shared utilities
```

## Debugging
Enable debug logging in config:
```yaml
log_level: DEBUG
```

## Releasing
- Update CHANGELOG.md
- Bump version in pyproject.toml
- Tag release: `git tag v0.1.0 && git push --tags`
- CI will build and create a GitHub release
