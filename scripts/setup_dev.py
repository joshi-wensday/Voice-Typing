#!/usr/bin/env python3
"""Development environment setup script.

This script automates the setup of the Voice Typing development environment:
- Creates virtual environment
- Installs dependencies
- Downloads default Whisper model
- Installs pre-commit hooks
- Verifies CUDA availability
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str, check: bool = True) -> bool:
    """Run a shell command with error handling.

    Args:
        cmd: Command and arguments to run
        description: Human-readable description of the operation
        check: Whether to exit on failure (default: True)

    Returns:
        True if successful, False otherwise
    """
    print(f"📦 {description}...")
    try:
        subprocess.run(cmd, check=True, shell=(os.name == "nt"))
        print(f"✅ {description} completed\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}\n")
        if check:
            sys.exit(1)
        return False


def check_python_version() -> None:
    """Verify Python version is 3.10 or higher."""
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ required")
        print(f"   Current version: {sys.version_info.major}.{sys.version_info.minor}")
        print("\nPlease install Python 3.10 or higher:")
        print("  https://www.python.org/downloads/")
        sys.exit(1)

    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} detected\n")


def check_cuda() -> None:
    """Check CUDA availability (optional)."""
    print("🔍 Checking CUDA availability...")
    try:
        import torch

        if torch.cuda.is_available():
            cuda_version = torch.version.cuda
            gpu_name = torch.cuda.get_device_name(0)
            print(f"✅ CUDA detected: {cuda_version}")
            print(f"   GPU: {gpu_name}\n")
        else:
            print("⚠️  CUDA not available (CPU mode will be used)")
            print("   For better performance, consider:")
            print("   - Installing CUDA Toolkit: https://developer.nvidia.com/cuda-downloads")
            print("   - Installing PyTorch with CUDA support\n")
    except ImportError:
        print("⚠️  PyTorch not installed yet (CUDA check skipped)\n")


def main() -> None:
    """Set up development environment."""
    print("🚀 Setting up Voice Typing development environment\n")

    # Check Python version
    check_python_version()

    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Change to project root
    os.chdir(project_root)

    # Create virtual environment
    venv_path = project_root / "venv"
    if not venv_path.exists():
        run_command(
            [sys.executable, "-m", "venv", "venv"], "Creating virtual environment"
        )
    else:
        print("✅ Virtual environment already exists\n")

    # Determine pip and python paths
    if os.name == "nt":
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
        activate_cmd = r"venv\Scripts\activate"
    else:
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
        activate_cmd = "source venv/bin/activate"

    # Upgrade pip
    run_command(
        [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
        "Upgrading pip",
    )

    # Install package in editable mode with dev dependencies
    run_command(
        [str(pip_path), "install", "-e", ".[dev]"],
        "Installing package with development dependencies",
    )

    # Check CUDA
    check_cuda()

    # Install pre-commit hooks
    pre_commit_installed = run_command(
        [str(python_path), "-m", "pre_commit", "install"],
        "Installing pre-commit hooks",
        check=False,
    )

    if not pre_commit_installed:
        print("⚠️  Pre-commit hooks not installed (optional)\n")

    # Download default Whisper model
    print("📥 Downloading Whisper base model (this may take a few minutes)...\n")
    model_downloaded = run_command(
        [str(python_path), "scripts/download_models.py", "--model", "base"],
        "Downloading Whisper base model",
        check=False,
    )

    if not model_downloaded:
        print("⚠️  Model download failed - you can download it later with:")
        print("   python scripts/download_models.py --model base\n")

    # Success message
    print("=" * 60)
    print("🎉 Development environment ready!")
    print("=" * 60)
    print("\n📝 Next steps:\n")
    print("  1. Activate virtual environment:")
    print(f"     {activate_cmd}")
    print("\n  2. Run tests:")
    print("     pytest tests/")
    print("\n  3. Start application:")
    print("     python -m voice_typing")
    print("\n  4. CLI test harness:")
    print("     python -m voice_typing --record-seconds 5")
    print("\n📖 Documentation:")
    print("   - docs/development.md - Development guide")
    print("   - docs/configuration.md - Configuration reference")
    print("   - CONTRIBUTING.md - Contribution guidelines")
    print()


if __name__ == "__main__":
    main()