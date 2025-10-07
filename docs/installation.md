# Installation Guide

This guide covers installation of Voice Typing for end users and developers.

## System Requirements

### Minimum Requirements
- **Operating System**: Windows 10 (64-bit) or Windows 11
- **Python**: 3.10 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Disk Space**: 4GB free (for models and dependencies)
- **Processor**: Any modern CPU

### Recommended for Best Performance
- **GPU**: NVIDIA GPU with CUDA support (GTX 1060 or better)
- **VRAM**: 4GB+ for medium/large models
- **RAM**: 16GB

## Quick Start (Automated Setup)

The easiest way to get started:

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/voice-typing.git
cd voice-typing

# 2. Run automated setup script
python scripts/setup_dev.py
```

The setup script will:
- Create a virtual environment
- Install all dependencies
- Download the default Whisper model (base)
- Install pre-commit hooks (for developers)
- Verify CUDA availability

Then activate the environment and run:

```bash
# Activate virtual environment
venv\Scripts\activate

# Run Voice Typing
python -m voice_typing
```

**Note**: You may need to run your terminal as Administrator for global hotkey registration.

## Manual Installation

If you prefer manual control or the automated script fails:

### Step 1: Install Python

1. Download Python 3.10+ from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Verify installation:
   ```bash
   python --version
   ```

### Step 2: Clone Repository

```bash
git clone https://github.com/yourusername/voice-typing.git
cd voice-typing
```

### Step 3: Create Virtual Environment

```bash
python -m venv venv
```

Activate the virtual environment:

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Windows (Git Bash):**
```bash
source venv/Scripts/activate
```

### Step 4: Install Dependencies

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install Voice Typing
pip install -e .
```

For developers, install with development tools:
```bash
pip install -e .[dev]
```

### Step 5: Download Whisper Model

Download the default model (base, ~140MB):

```bash
python scripts/download_models.py --model base
```

Or choose a different model size:

```bash
# Fastest, lowest accuracy (39M params, ~75MB)
python scripts/download_models.py --model tiny

# Better accuracy, slower (244M params, ~480MB)
python scripts/download_models.py --model small

# High accuracy, requires GPU (769M params, ~1.5GB)
python scripts/download_models.py --model medium

# Best accuracy, requires powerful GPU (1550M params, ~3GB)
python scripts/download_models.py --model large-v2
```

### Step 6: Run Application

```bash
python -m voice_typing
```

A system tray icon should appear. Press `Ctrl+Shift+Space` to start dictating!

## GPU Acceleration (Optional but Recommended)

For significantly faster transcription, enable GPU acceleration:

### Check GPU Compatibility

Your GPU must support CUDA. Check compatibility:
- [NVIDIA CUDA GPUs](https://developer.nvidia.com/cuda-gpus)

### Install CUDA Toolkit

1. Download from [NVIDIA CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)
2. Install following NVIDIA's instructions
3. Verify installation:
   ```bash
   nvcc --version
   ```

### Verify GPU is Used

After installation, Voice Typing will automatically use GPU if available.

To verify:
```bash
# CLI test mode
python -m voice_typing --record-seconds 5
```

Look for output mentioning "cuda" or GPU name. If using CPU, you'll see slower transcription times (>5s).

### Troubleshooting GPU Issues

If GPU is not detected:

1. **Check PyTorch CUDA support:**
   ```bash
   python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
   ```

2. **Reinstall PyTorch with CUDA:**
   ```bash
   pip uninstall torch
   pip install torch --index-url https://download.pytorch.org/whl/cu118
   ```

3. **Check NVIDIA drivers:**
   - Update to latest drivers from [NVIDIA website](https://www.nvidia.com/Download/index.aspx)

4. **Fallback to CPU:**
   If GPU issues persist, edit `~/.voice-typing/config.yaml`:
   ```yaml
   stt:
     device: cpu
     compute_type: float32
   ```

## Configuration

After first run, configuration is stored in:
```
C:\Users\YourName\.voice-typing\config.yaml
```

See [Configuration Guide](configuration.md) for all options.

## Troubleshooting

### Issue: "Hotkey registration failed"

**Solution**: Run terminal as Administrator (required for global hotkeys on Windows).

Right-click terminal → "Run as administrator"

### Issue: "ModuleNotFoundError: No module named 'voice_typing'"

**Solution**: Install package in editable mode:
```bash
cd voice-typing
pip install -e .
```

### Issue: "Model download fails"

**Solutions**:
- Check internet connection
- Ensure you have ~1-3GB free disk space
- Try a smaller model: `--model tiny`
- Download manually from [Hugging Face](https://huggingface.co/guillaumekln/faster-whisper-base)

### Issue: "Text not inserting in applications"

**Solutions**:
- Try different applications (Notepad works reliably)
- Check output method in config:
  ```yaml
  output:
    primary_method: clipboard  # Fallback if keyboard fails
  ```
- Some apps (games, admin apps) may block input
- Run Voice Typing as Administrator

### Issue: High latency (>5 seconds)

**Solutions**:
- Use a smaller model: `base` or `tiny`
- Enable GPU acceleration (see above)
- Check CPU usage (close other apps)
- Reduce beam_size in config:
  ```yaml
  decoding:
    beam_size: 1  # Fastest, slight accuracy loss
  ```

### Issue: Poor transcription accuracy

**Solutions**:
- Use a larger model: `small` or `medium`
- Speak clearly and at moderate pace
- Reduce background noise
- Check microphone quality/positioning
- Adjust audio device in Settings UI

### Issue: Application won't start

**Solutions**:
1. Check Python version: `python --version` (must be 3.10+)
2. Reinstall dependencies: `pip install -e . --force-reinstall`
3. Check for errors: Run with debug logging
   ```bash
   python -m voice_typing
   # Check console output for errors
   ```
4. Try CLI test mode to isolate issues:
   ```bash
   python -m voice_typing --record-seconds 5
   ```

### Issue: "CUDA out of memory"

**Solution**: Use a smaller model or reduce batch size:
```yaml
stt:
  model: base  # or tiny
  compute_type: int8  # Reduces memory usage
```

## Uninstallation

To completely remove Voice Typing:

```bash
# 1. Deactivate virtual environment
deactivate

# 2. Remove project directory
cd ..
rmdir /s voice-typing

# 3. Remove config directory (optional)
rmdir /s %USERPROFILE%\.voice-typing

# 4. Remove model cache (optional, saves ~1-3GB)
rmdir /s %USERPROFILE%\.cache\huggingface
```

## Next Steps

After installation:

1. **Configure**: Edit `~/.voice-typing/config.yaml` or use Settings UI (right-click overlay)
2. **Test**: Press `Ctrl+Shift+Space` in Notepad and speak
3. **Customize**: Add custom voice commands in config
4. **Optimize**: Adjust model size and parameters for your hardware

See:
- [Configuration Guide](configuration.md) - All configuration options
- [Architecture Overview](architecture.md) - How Voice Typing works
- [Development Guide](development.md) - For contributors

## Getting Help

If you encounter issues not covered here:

1. Check [GitHub Issues](https://github.com/yourusername/voice-typing/issues)
2. Search [Discussions](https://github.com/yourusername/voice-typing/discussions)
3. Create a new issue with:
   - Your OS version and Python version
   - Error messages or console output
   - Steps to reproduce
   - Your config.yaml (remove sensitive info)
