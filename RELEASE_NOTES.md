# Vype v1.0.0 - Initial Release 🎉

**Release Date:** October 10, 2025

## Overview

Vype (Voice + Type) is a local, privacy-focused speech-to-text application for Windows that runs entirely on your PC with no cloud dependencies.

## 🎯 What's New

### Core Features
- ✅ **Global Hotkey Activation** - Customizable hotkey (default: `Ctrl+Shift+Space`)
- ✅ **100% Local Processing** - Your audio never leaves your machine
- ✅ **Fast Transcription** - <3 second latency using OpenAI Whisper
- ✅ **Voice Commands** - "new line", "period", "stop dictation", and more
- ✅ **Flexible Punctuation** - Auto-punctuation with manual override options

### Modern UI
- ✅ **Circular Audio Spectrum Visualizer** - Real-time FFT analysis with 64 frequency bands
- ✅ **Glassmorphism Design** - Modern, professional settings window
- ✅ **Full Theme Customization** - Choose your own colors for idle/recording/processing states
- ✅ **Transparency Controls** - Adjust opacity for overlay and settings window
- ✅ **Resizable Visualizer** - Scale from 60px to 150px
- ✅ **Interactive Hotkey Capture** - Set custom hotkeys with visual feedback

### Model Management
- ✅ **Easy Model Installation** - Download models directly from the app
- ✅ **Model Testing & Benchmarking** - Compare performance on your hardware
- ✅ **10 Curated Models** - From tiny (39M) to large-v3 (1550M parameters)
- ✅ **HuggingFace Integration** - Install custom models from URLs

## 📥 Installation

### Windows Installer (Recommended)

Download and run `vype-setup-v1.0.0.exe` from the Assets section below.

**What's included:**
- Complete application with all dependencies
- Desktop shortcut
- Start Menu integration
- Uninstaller

**System Requirements:**
- Windows 10/11 (64-bit)
- 4GB+ RAM
- 2GB+ free disk space (for models)
- NVIDIA GPU with CUDA support (recommended, CPU also works)

**First Launch:**
1. Launch Vype from the desktop shortcut or Start Menu
2. You'll be prompted to download a speech model
3. Select a model (we recommend "base" for most users)
4. Wait for download to complete
5. Start dictating!

**Note:** Windows may show a SmartScreen warning for unsigned applications. Click "More info" → "Run anyway" to proceed.

## 🐛 Bug Fixes

This release includes fixes for all known issues:

- ✅ Fixed dropdown options not displaying in settings window
- ✅ Fixed tab names being truncated in settings window
- ✅ Removed white circle hover effect on circular UI
- ✅ Fixed color picker window opening underneath settings window
- ✅ Fixed hotkey not activating consistently (race condition)
- ✅ Fixed Save and Close buttons being cut off
- ✅ Fixed text boxes being too small in settings tabs
- ✅ Fixed text alignment in settings tabs

## ⚡ Performance Improvements

- Increased audio visualizer refresh rate from 60fps to 90fps for smoother updates
- Improved FFT discretization with 64 frequency bands (up from 48)
- Enhanced audio spectrum analysis with better noise filtering
- Louder sounds now have far higher weighting than quiet sounds
- Added exponential curve (^2.5) for aggressive noise suppression
- Implemented spatial smoothing for smoother frequency transitions

## 🔧 Technical Details

### What's Under the Hood
- Python 3.10+
- OpenAI Whisper via faster-whisper for optimized inference
- Real-time audio capture with 16kHz sampling
- FFT-based spectrum analysis for audio visualization
- Win32 API integration for global hotkeys
- Modern Tkinter-based UI with custom widgets

### For Developers
- Modular architecture with clean interfaces
- Comprehensive test suite
- Pre-commit hooks for code quality
- Detailed documentation in `/docs`

See the [README](https://github.com/joshi-wensday/Voice-Typing/blob/main/README.md) for development setup instructions.

## 📖 Documentation

- [Installation Guide](https://github.com/joshi-wensday/Voice-Typing#-quick-start)
- [Usage Guide](https://github.com/joshi-wensday/Voice-Typing#-usage)
- [Configuration Guide](https://github.com/joshi-wensday/Voice-Typing/blob/main/docs/configuration.md)
- [Building from Source](https://github.com/joshi-wensday/Voice-Typing/blob/main/docs/building.md)

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - STT model
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized inference
- Inspired by [Talon Voice](https://talonvoice.com/) and commercial solutions

## 📜 License

MIT License - See [LICENSE](https://github.com/joshi-wensday/Voice-Typing/blob/main/LICENSE) for details.

---

**Full Changelog:** https://github.com/joshi-wensday/Voice-Typing/commits/v1.0.0

