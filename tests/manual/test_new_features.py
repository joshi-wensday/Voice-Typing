#!/usr/bin/env python3
"""Manual Canary STT test.

Records audio for N seconds and prints the Canary transcription.
Run from the repo root:
    python tests/manual/test_new_features.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vype.audio.capture import AudioCapture
from vype.config.manager import ConfigManager
from vype.stt.canary_engine import CanaryQwenEngine

RECORD_SECONDS = 5


def main() -> None:
    cfg = ConfigManager()
    a = cfg.config.audio
    s = cfg.config.stt

    audio = AudioCapture(
        sample_rate=a.sample_rate,
        channels=a.channels,
        device_id=a.device_id,
        chunk_duration=a.chunk_duration,
    )

    print(f"Recording for {RECORD_SECONDS}s — speak now...")
    audio.start_recording()
    try:
        time.sleep(RECORD_SECONDS)
    finally:
        samples = audio.stop_recording()

    print(f"Captured {len(samples)} samples @ {a.sample_rate} Hz")

    engine = CanaryQwenEngine(
        model=s.model,
        device=s.device,
        language=s.language,
        max_new_tokens=s.max_new_tokens,
        enable_pnc=s.enable_pnc,
        context_tail_chars=s.context_tail_chars,
    )
    print(f"Loading model: {s.model} on {s.device} ...")
    engine.preload()

    t0 = time.time()
    result = engine.transcribe(samples, sample_rate=a.sample_rate)
    latency = time.time() - t0

    print(f"\nTranscription:\n  {result.text}")
    print(f"\nLatency: {latency:.2f}s")


if __name__ == "__main__":
    main()
