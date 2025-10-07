# Installation

## Prerequisites
- Windows 10/11
- Python 3.10+
- (Optional) NVIDIA GPU with CUDA for faster inference

## Steps
```bash
# Clone repository
git clone https://github.com/yourusername/voice-typing.git
cd voice-typing

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install package
pip install -e .

# (Optional) Install dev tools
pip install -e .[dev]

# Download Whisper model (one-time)
python scripts/download_models.py --model base

# Run the application (later phases)
python -m voice_typing
```

## Troubleshooting
- Run shell as Administrator for global hotkeys
- If GPU is not used, ensure CUDA is installed and supported by your hardware
