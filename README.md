# 🎤 Vype - Local Speech-to-Text for Windows

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)

**System-wide voice dictation that runs entirely locally. No cloud, no subscriptions, just your voice and your PC.**

> **Vype** = Voice + Type. Your personal voice dictation assistant.

## ✨ Features

### Core Functionality
- 🎯 **Global Hotkey Activation** - Customizable hotkey (default: `Ctrl+Shift+Space`)
- 🔒 **100% Local Processing** - Your audio never leaves your machine
- ⚡ **Fast Transcription** - <3 second latency using OpenAI Whisper
- 🗣️ **Voice Commands** - "new line", "period", "stop dictation"
- 🎛️ **Flexible Punctuation** - Auto-punctuation with manual override options

### Modern UI & Customization
- 🎨 **Circular Audio Spectrum Visualizer** - Real-time FFT analysis with 48 frequency bands
- 💎 **Glassmorphism Design** - Modern, professional settings window
- 🌈 **Full Theme Customization** - Choose your own colors for idle/recording/processing states
- 🔍 **Transparency Controls** - Adjust opacity for overlay and settings window
- 📏 **Resizable Visualizer** - Scale from 60px to 150px
- ⌨️ **Interactive Hotkey Capture** - Set custom hotkeys like in a video game

### Model Management
- 📦 **Easy Model Installation** - Download models directly from the app
- 🧪 **Model Testing & Benchmarking** - Compare performance on your hardware
- 📊 **Performance Metrics** - See speed and accuracy for each model
- 🔄 **HuggingFace Integration** - Install custom models from URLs
- 💾 **10 Curated Models** - From tiny (39M) to large-v3 (1550M parameters)

### Advanced Features
- 🔧 **Fully Customizable** - Add your own commands and shortcuts
- 📦 **Modular Architecture** - Swap STT engines without breaking anything
- 🎨 **Custom Styled Widgets** - Modern dropdowns, sliders, and color pickers

## 🚀 Quick Start

### 📥 Download

**For End Users (Recommended):**

Download the Windows installer from the [Releases page](https://github.com/joshi-wensday/Voice-Typing/releases/latest):

- **[Download Vype Setup v1.0.0](https://github.com/joshi-wensday/Voice-Typing/releases/download/v1.0.0/vype-setup-v1.0.0.exe)** (77 MB)

The installer includes:
- ✅ Complete application with all dependencies
- ✅ Desktop shortcut creation
- ✅ Start Menu integration
- ✅ Automatic updates (future)
- ✅ Uninstaller

**For Developers:**

See the [Development Setup](#for-developers) section below.

### System Requirements

- Windows 10/11 (64-bit)
- 4GB+ RAM
- 2GB+ free disk space (for models)
- NVIDIA GPU with CUDA support (recommended, CPU also works)

### Installation (End Users)

1. Download the installer from the link above
2. Run `vype-setup-v1.0.0.exe`
3. Follow the installation wizard
4. Launch Vype from the desktop shortcut or Start Menu
5. First launch will prompt you to download a speech model

**Note:** Windows may show a SmartScreen warning for unsigned applications. Click "More info" → "Run anyway" to proceed.

### For Developers

**Prerequisites:**
- Python 3.10 or higher
- Git

**Quick Setup:**

```bash
# Clone the repository
git clone https://github.com/joshi-wensday/Voice-Typing.git
cd Voice-Typing

# Run the automated setup script
python scripts/setup_dev.py
```

The setup script will:
- Create a virtual environment
- Install all dependencies
- Download the default Whisper model
- Set up pre-commit hooks

**Manual Setup:**

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -e .

# Download Whisper model (one-time)
python scripts/download_models.py --model base
```

**Running from Source:**

```bash
# Activate virtual environment (if not already active)
venv\Scripts\activate

# Run Vype
python -m vype
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

## 🎨 Modern UI Features

Voice Typing features a completely redesigned, professional-grade interface:

### Circular Audio Visualizer
- **Dynamic Gradients**: Colors change based on state (idle/recording/processing)
  - **Idle**: Calm blue/purple with gentle breathing animation
  - **Recording**: Energetic red/orange with active pulsing
  - **Processing**: Yellow/gold with smooth rotation
- **Waveform Visualization**: 48 circular frequency bars that react to your voice
- **Smooth Animations**: 30 FPS performance with optimized rendering
- **Interactive Effects**: Hover highlights, click ripples, drag trails

### Glassmorphism Settings Window
- **Modern Dark Theme**: Semi-transparent background with beautiful gradients
- **Custom Widgets**: Rounded buttons with hover effects, styled input fields
- **Smooth Animations**: Fade-in transitions, success confirmations
- **Professional Layout**: Tabbed interface with spacious, organized design

See [UI Modernization Documentation](docs/ui_modernization.md) for complete details.

### Model Management

Vype includes a comprehensive model management system:

**Installing Models:**
1. Open Settings → Models tab
2. Select a model from the dropdown (tiny, base, small, medium, large-v2, large-v3)
3. Click "Download Model" - Vype handles everything automatically
4. Or paste a HuggingFace URL for custom models

**Testing Models:**
- Click "Test All Models" to benchmark installed models
- See real-time comparison of speed vs. accuracy
- Get automatic recommendations for your hardware

**Manual Installation:**
- Click "Open Model Folder" to access the model directory
- Drop model files directly into the folder
- Click "Refresh" to detect new models

### Customization

**Appearance Settings** (Settings → Appearance):
- Choose custom colors for idle, recording, and processing states
- Adjust window transparency (0.7 - 1.0)
- Resize the visualizer (60px - 150px)
- All changes apply instantly

**Hotkey Configuration:**
- Click the hotkey field in Settings → General
- Press your desired key combination
- Visual feedback shows keys as you press them
- Confirm with checkmark or cancel with X

### Testing the UI

Run the visual test suite to explore all UI features:

```bash
python test_ui_modernization.py
```

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

## 🎯 Why Vype?

| Commercial Solutions | Vype |
|---------------------|------|
| ❌ $10-30/month subscriptions | ✅ Free and open source |
| ❌ Cloud processing (privacy concerns) | ✅ 100% local processing |
| ❌ Requires internet connection | ✅ Works offline |
| ❌ Black box systems | ✅ Transparent, customizable code |
| ❌ Limited command customization | ✅ Fully extensible command system |

## 🏗️ Architecture

Vype uses a modular architecture that separates concerns:

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
- [Bug Reports](https://github.com/joshi-wensday/Voice-Typing/issues/new?template=bug_report.md)
- [Feature Requests](https://github.com/joshi-wensday/Voice-Typing/issues/new?template=feature_request.md)

## 📋 Roadmap

- [x] Core STT pipeline with Whisper
- [x] Voice command processing
- [x] Circular audio visualizer
- [ ] Multi-language support
- [ ] Streaming transcription mode
- [ ] macOS/Linux support
- [ ] Plugin system for custom STT engines

See [Issues](https://github.com/joshi-wensday/Voice-Typing/issues) for full roadmap.

## 📜 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - STT model
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized inference
- Inspired by [Talon Voice](https://talonvoice.com/) and commercial solutions

## 💬 Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/joshi-wensday/Voice-Typing/issues)
- 💬 [Discussions](https://github.com/joshi-wensday/Voice-Typing/discussions)

---

Made with ❤️ by developers who believe in privacy and open source.
