#!/usr/bin/env python3
"""Download Whisper models for offline use."""

from __future__ import annotations

import argparse
import sys

from faster_whisper import WhisperModel


def download_model(name: str, device: str = "auto") -> None:
    # Initializing the model downloads and caches it.
    print(f"Downloading model: {name} (device={device}) ...")
    _ = WhisperModel(name, device=device)
    print("✅ Download complete.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Whisper models")
    parser.add_argument("--model", required=True, help="Model name (e.g., tiny, base, small, medium, large-v2)")
    parser.add_argument("--device", default="auto", help="Device (auto, cuda, cpu)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    download_model(args.model, args.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
