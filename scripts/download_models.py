#!/usr/bin/env python3
"""Download Whisper models for offline use.

This script pre-downloads Whisper models using faster-whisper's model manager.
Models are cached locally for offline transcription.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Error: faster-whisper not installed.")
    print("Install with: pip install faster-whisper")
    sys.exit(1)


AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]


def download_model(model_name: str, device: str = "auto", compute_type: str = "float16") -> None:
    """Download a Whisper model.

    Args:
        model_name: Model size (tiny, base, small, medium, large-v2, large-v3)
        device: Device to use (auto, cuda, cpu)
        compute_type: Compute type (float16, float32, int8)
    """
    if model_name not in AVAILABLE_MODELS:
        print(f"Error: Unknown model '{model_name}'")
        print(f"Available models: {', '.join(AVAILABLE_MODELS)}")
        sys.exit(1)

    print(f"📥 Downloading Whisper model: {model_name}")
    print(f"   Device: {device}")
    print(f"   Compute type: {compute_type}")
    print()

    try:
        # Loading the model will download it if not cached
        print("Initializing model (this may take a few minutes)...")
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        print("✅ Model downloaded successfully!")
        print()

        # Get cache location
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        print(f"📁 Model cached in: {cache_dir}")
        print()

        # Warmup inference to verify installation
        print("🔥 Running warmup inference...")
        import numpy as np

        dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        segments, _ = model.transcribe(dummy_audio, beam_size=1)
        list(segments)  # Force evaluation

        print("✅ Model is ready to use!")

    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        print()
        print("Troubleshooting:")
        print("  - Ensure you have internet connection")
        print("  - Check if you have enough disk space (~1-3GB per model)")
        print("  - If using CUDA, ensure CUDA toolkit is installed")
        print("  - Try with --compute-type float32 if float16 fails")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download Whisper models for Voice Typing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/download_models.py --model base
  python scripts/download_models.py --model small --device cuda
  python scripts/download_models.py --model tiny --compute-type float32

Available models (size, accuracy):
  tiny       - 39M params  (fastest, lowest accuracy)
  base       - 74M params  (recommended for most users)
  small      - 244M params (better accuracy, slower)
  medium     - 769M params (high accuracy, requires GPU)
  large-v2   - 1550M params (best accuracy, requires GPU)
  large-v3   - 1550M params (latest, best accuracy, requires GPU)
""",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="base",
        choices=AVAILABLE_MODELS,
        help="Model size to download (default: base)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Device to use (default: auto)",
    )
    parser.add_argument(
        "--compute-type",
        type=str,
        default="float16",
        choices=["float16", "float32", "int8"],
        help="Compute type (default: float16)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available models",
    )

    args = parser.parse_args()

    if args.all:
        print("📦 Downloading all models (this will take a while)...")
        print()
        for model in AVAILABLE_MODELS:
            download_model(model, args.device, args.compute_type)
            print()
    else:
        download_model(args.model, args.device, args.compute_type)

    print("🎉 All done! You can now run Voice Typing offline.")


if __name__ == "__main__":
    main()