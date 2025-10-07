#!/usr/bin/env python3
"""Development environment setup script for Voice Typing."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> None:
    """Run a shell command with error handling."""
    print(f"📦 {description}...")
    try:
        subprocess.run(cmd, check=True, shell=(os.name == "nt"))
        print(f"✅ {description} completed\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}\n")
        sys.exit(1)


def main() -> None:
    """Set up development environment."""
    print("🚀 Setting up Voice Typing development environment\n")

    # Check Python version
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ required")
        sys.exit(1)

    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected\n")

    # Create virtual environment
    venv_path = Path("venv")
    if not venv_path.exists():
        run_command([sys.executable, "-m", "venv", "venv"], "Creating virtual environment")
    else:
        print("✅ Virtual environment already exists\n")

    # Determine pip/python path
    if os.name == "nt":
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"

    # Upgrade pip
    run_command([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], "Upgrading pip")

    # Install package in editable mode with dev dependencies
    run_command([str(pip_path), "install", "-e", ".[dev]"], "Installing package with development dependencies")

    # Install pre-commit hooks
    run_command([str(python_path), "-m", "pre_commit", "install"], "Installing pre-commit hooks")

    # Download default Whisper model
    run_command([str(python_path), "scripts/download_models.py", "--model", "base"], "Downloading Whisper base model")

    print("🎉 Development environment ready!")
    print("\n📝 Next steps:")
    print("  1. Activate virtual environment:")
    if os.name == "nt":
        print("     venv\\Scripts\\activate")
    else:
        print("     source venv/bin/activate")
    print("  2. Run tests: pytest tests/")
    print("  3. Start application: python -m voice_typing")
    print("\n📖 See docs/development.md for more information")


if __name__ == "__main__":
    main()
