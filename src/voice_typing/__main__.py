"""Voice Typing entry point.

Default behavior: launch tray + hotkey. Use --record-seconds for CLI test harness.
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from .audio.capture import AudioCapture
from .config.manager import ConfigManager
from .stt.whisper_engine import FasterWhisperEngine
from .controller import VoiceTypingController
from .ui.hotkey import HotkeyManager
from .ui.tray import TrayApp


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Voice Typing")
    p.add_argument("--record-seconds", type=float, default=None, help="CLI test harness: record duration in seconds")
    return p.parse_args()


def _run_cli(record_seconds: float) -> None:
    cfg = ConfigManager()
    print("Voice Typing: CLI STT test")
    print(f"Config: {cfg.config_path}")

    a_cfg = cfg.config.audio
    audio = AudioCapture(
        sample_rate=a_cfg.sample_rate,
        channels=a_cfg.channels,
        device_id=a_cfg.device_id,
        chunk_duration=a_cfg.chunk_duration,
    )

    print(f"\nRecording for {record_seconds:.1f}s ... Press Ctrl+C to abort.")
    audio.start_recording()
    try:
        time.sleep(record_seconds)
    finally:
        samples = audio.stop_recording()

    print(f"Captured {samples.shape[0]} samples @ {a_cfg.sample_rate} Hz")

    s_cfg = cfg.config.stt
    stt = FasterWhisperEngine(
        model=s_cfg.model,
        device=s_cfg.device,
        compute_type=s_cfg.compute_type,
        language=s_cfg.language,
    )
    stt.preload()

    t0 = time.time()
    result = stt.transcribe(samples, sample_rate=a_cfg.sample_rate)
    latency = time.time() - t0

    print("\nTranscribed Text:")
    print(result.text)
    print(f"\nLatency: {latency:.2f}s")


def _run_app() -> None:
    cfgm = ConfigManager()
    controller = VoiceTypingController(cfgm)

    # Tray
    tray = TrayApp(on_toggle=controller.toggle, on_exit=lambda: None)
    tray.run()
    controller.on_status_change = tray.set_status

    # Hotkey (default to ctrl+alt+space)
    hk = cfgm.config.ui.hotkey or "ctrl+alt+space"
    hotkey = HotkeyManager(hotkey=hk, on_toggle=controller.toggle)
    if not hotkey.register():
        print("Warning: failed to register hotkey. Try running as Administrator.")
    print(f"Voice Typing running. Hotkey: {hk}")
    hotkey.wait()


def main() -> None:
    args = _parse_args()
    if args.record_seconds is not None:
        _run_cli(args.record_seconds)
    else:
        _run_app()


if __name__ == "__main__":
    main()
