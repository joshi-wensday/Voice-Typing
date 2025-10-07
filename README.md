# 🎤 Voice Typing - Local Speech-to-Text for Windows

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)

**System-wide voice dictation that runs entirely locally. No cloud, no subscriptions, just your voice and your PC.**

## ✨ Features

- 🎯 **Global Hotkey Activation** - Press `Ctrl+Shift+Space` in any application
- 🔒 **100% Local Processing** - Your audio never leaves your machine
- ⚡ **Fast Transcription** - <3 second latency using OpenAI Whisper
- 🎨 **Real-time Visualization** - Circular audio waveform overlay
- 🗣️ **Voice Commands** - "new line", "period", "stop dictation"
- 🔧 **Fully Customizable** - Add your own commands and shortcuts
- 🎛️ **Flexible Punctuation** - Auto-punctuation with manual override options
- 📦 **Modular Architecture** - Swap STT engines without breaking anything

## 🚀 Quick Start

### Prerequisites

- Windows 10/11
- Python 3.10 or higher
- NVIDIA GPU with CUDA support (recommended, CPU also works)
- 4GB+ free disk space (for models)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/voice-typing.git
cd voice-typing

# Run the automated setup script
python scripts/setup_dev.py
```

The setup script will:
- Create a virtual environment
- Install all dependencies
- Download the default Whisper model
- Set up pre-commit hooks

### Manual Installation

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -e .

# Download Whisper model (one-time)
python scripts/download_models.py --model base
```

### Running the Application

```bash
# Activate virtual environment (if not already active)
venv\Scripts\activate

# Run Voice Typing
python -m voice_typing
```

**Note:** On Windows, the application requires administrator privileges to register global hotkeys.

## 📖 Usage

1. **Launch the application** - A system tray icon will appear
2. **Click any text field** in any application
3. **Press `Ctrl+Shift+Space`** to start dictating
4. **Speak naturally** - A circular visualizer shows audio levels
5. **Press `Ctrl+Shift+Space` again** to stop and insert text

### Voice Commands

- `"new line"` - Insert line break
- `"period"` / `"comma"` / `"question mark"` - Insert punctuation
- `"stop dictation"` - End session immediately

### UI Controls

- **Left-click visualizer** - Mute/unmute
- **Right-click visualizer** - Open settings
- **Drag visualizer** - Move to preferred screen position

## ⚙️ Configuration

Configuration is stored in `~/.voice-typing/config.yaml`. You can edit this file directly or use the settings UI.

Example configuration:

```yaml
stt:
  model: base  # tiny, base, small, medium, large-v2
  device: auto  # auto, cuda, cpu

punctuation:
  mode: hybrid  # auto, manual, hybrid
  auto_capitalize: true

ui:
  hotkey: ctrl+shift+space
  show_visualizer: true
```

See [`config.example.yaml`](config.example.yaml) for all available options.

## 🎯 Why Voice Typing?

| Commercial Solutions | Voice Typing |
|---------------------|--------------|
| ❌ $10-30/month subscriptions | ✅ Free and open source |
| ❌ Cloud processing (privacy concerns) | ✅ 100% local processing |
| ❌ Requires internet connection | ✅ Works offline |
| ❌ Black box systems | ✅ Transparent, customizable code |
| ❌ Limited command customization | ✅ Fully extensible command system |

## 🏗️ Architecture

Voice Typing uses a modular architecture that separates concerns:

```
Audio Capture → STT Engine → Command Processor → Output Handler
                    ↓
                UI Layer
```

Each module implements a clean interface, making it easy to:
- Swap Whisper for another STT engine
- Add new voice commands without touching core code
- Test components in isolation

See [Architecture Documentation](docs/architecture.md) for details.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Quick Links:
- [Development Setup](docs/development.md)
- [Bug Reports](https://github.com/yourusername/voice-typing/issues/new?template=bug_report.md)
- [Feature Requests](https://github.com/yourusername/voice-typing/issues/new?template=feature_request.md)

## 📋 Roadmap

- [x] Core STT pipeline with Whisper
- [x] Voice command processing
- [x] Circular audio visualizer
- [ ] Multi-language support
- [ ] Streaming transcription mode
- [ ] macOS/Linux support
- [ ] Plugin system for custom STT engines

See [Issues](https://github.com/yourusername/voice-typing/issues) for full roadmap.

## 📜 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - STT model
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized inference
- Inspired by [Talon Voice](https://talonvoice.com/) and commercial solutions

## 💬 Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/yourusername/voice-typing/issues)
- 💬 [Discussions](https://github.com/yourusername/voice-typing/discussions)

---

Made with ❤️ by developers who believe in privacy and open source.
