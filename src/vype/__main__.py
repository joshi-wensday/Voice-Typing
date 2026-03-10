"""Vype entry point.

Default behavior: launch tray + hotkey. Use --record-seconds for CLI test harness.
"""

from __future__ import annotations

import argparse
import time
import tkinter as tk

from vype.audio.capture import AudioCapture
from vype.config.manager import ConfigManager
from vype.stt.canary_engine import CanaryQwenEngine
from vype.controller import VoiceTypingController
from vype.ui.hotkey import HotkeyManager
from vype.ui.hotkey_win32 import Win32Hotkey
from vype.ui.tray import TrayApp
from vype.ui.settings_window import SettingsWindow
from vype.ui.overlay import Overlay
from vype.utils.system import SingleInstance
from vype.utils.logger import setup_logging, get_logger


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vype - Local Voice Dictation")
    p.add_argument(
        "--record-seconds",
        type=float,
        default=None,
        help="CLI test harness: record N seconds and print the transcription",
    )
    return p.parse_args()


def _run_cli(record_seconds: float) -> None:
    """Record audio for the given duration and print the Canary transcription."""
    cfg = ConfigManager()
    print("Vype: CLI STT test")
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
    stt = CanaryQwenEngine(
        model=s_cfg.model,
        device=s_cfg.device,
        language=s_cfg.language,
        max_new_tokens=s_cfg.max_new_tokens,
        enable_pnc=s_cfg.enable_pnc,
        context_tail_chars=s_cfg.context_tail_chars,
    )
    stt.preload()

    t0 = time.time()
    result = stt.transcribe(samples, sample_rate=a_cfg.sample_rate)
    latency = time.time() - t0

    print("\nTranscribed Text:")
    print(result.text)
    print(f"\nLatency: {latency:.2f}s")


def _run_app() -> None:
    # Initialize config first to get log settings
    cfgm = ConfigManager()

    # Set up logging
    logger = setup_logging(
        level=cfgm.config.log_level, log_file=cfgm.config.log_file
    )
    logger.info("Vype starting...")
    logger.info(f"Config loaded from: {cfgm.config_path}")

    # Check for single instance
    instance = SingleInstance()
    if not instance.acquire():
        logger.warning("Vype is already running")
        print("Vype is already running.")
        return

    try:
        controller = VoiceTypingController(cfgm)
    except Exception as e:
        logger.error(f"Failed to initialize controller: {e}", exc_info=True)
        print(f"Error: Failed to initialize application: {e}")
        return

    # ── Preload STT model in background ──────────────────────────────────
    # Starts loading while the UI is being built so the first hotkey press
    # is instant rather than waiting 30–60 s for the model to load.
    # The LoRA adapter message ("LoRA adapter installed") is normal — NeMo
    # reconstructs the model architecture in memory on every Python process
    # start.  It is NOT a re-download; weights are already cached locally.
    import threading as _threading
    _threading.Thread(
        target=controller.stt.preload,
        daemon=True,
        name="vype-model-preload",
    ).start()
    logger.info("STT model preload started in background (first hotkey will not block)")

    # Tk root for settings/overlay on main thread
    root = tk.Tk()
    root.withdraw()

    # Settings window
    settings = SettingsWindow(cfgm, root=root)

    # ── Integrated output window ───────────────────────────────────────────
    # Shown by default (integrated_output_enabled=True in schema.py).
    # Refinement layers (pause / final) are off by default — the per-segment
    # draft is already very accurate and refinement can be enabled in Settings.
    _output_win = None
    if cfgm.config.ui.integrated_output_enabled:
        from vype.stt.progressive_transcriber import ProgressiveTranscriber
        from vype.ui.integrated_output import IntegratedOutputWindow

        _output_win = IntegratedOutputWindow(root)
        _prog = ProgressiveTranscriber(
            engine=controller.stt,
            sample_rate=cfgm.config.audio.sample_rate,
            pause_sec=cfgm.config.ui.integrated_output_pause_sec,
            pause_refine=cfgm.config.ui.integrated_output_pause_refine,
        )
        # All callbacks must be dispatched via root.after — Tk is not thread-safe
        _prog.on_draft_text   = lambda t: root.after(0, _output_win.append_draft, t)
        _prog.on_refined_text = lambda t, f: root.after(0, _output_win.replace_refined, t, f)
        _prog.on_status       = lambda s: root.after(0, _output_win.set_status, s)
        _output_win.on_clear  = _prog.reset

        controller.progressive = _prog
        _output_win.show()
        logger.info(
            "Integrated output window enabled "
            "(pause_refine=%s, final_refine=%s)",
            cfgm.config.ui.integrated_output_pause_refine,
            cfgm.config.ui.integrated_output_final_refine,
        )

    # Overlay
    overlay = Overlay(
        get_level=controller.audio.get_level,
        size=cfgm.config.ui.visualizer_size,
        opacity=cfgm.config.ui.visualizer_opacity,
        position=cfgm.config.ui.visualizer_position,
        root=root,
        config_manager=cfgm,
    )
    overlay.on_toggle = controller.toggle
    overlay.on_settings = settings.show
    if _output_win is not None:
        overlay.on_output_toggle = _output_win.toggle
    overlay.set_audio_capture(controller.audio)
    if cfgm.config.ui.show_visualizer:
        overlay.show()

    # Tray (runs in its own thread); Exit will quit Tk
    tray = TrayApp(on_toggle=controller.toggle, on_exit=root.quit, on_settings=settings.show)
    tray.run()

    # Connect status changes to both tray and overlay
    def on_status_change(status: str) -> None:
        tray.set_status(status)
        overlay.set_state(status)

    controller.on_status_change = on_status_change

    # Hotkey candidates: config first, then fallbacks (runs in bg threads)
    preferred = cfgm.config.ui.hotkey or "ctrl+alt+space"
    candidates = [preferred, "ctrl+shift+space", "ctrl+alt+shift+space", "ctrl+alt+z"]

    try:
        win32_hk = Win32Hotkey(hotkey=preferred, on_toggle=controller.toggle)
        if win32_hk.is_available() and win32_hk.register_from_candidates(candidates):
            active = win32_hk.active_spec or preferred
            logger.info(f"Hotkey registered (Win32): {active}")
            print(f"Hotkey (Win32): {active}")
            tray.set_tooltip(f"Vype (Win32) — {active}")
        else:
            hotkey = HotkeyManager(hotkey=preferred, on_toggle=controller.toggle)
            if not hotkey.register():
                logger.warning(f"Hotkey registration failed: {preferred}")
                print("Hotkey (keyboard) registration failed. Try another combo in config.ui.hotkey.")
            else:
                logger.info(f"Hotkey registered (keyboard): {preferred}")
            print(f"Hotkey (keyboard): {preferred}")
            tray.set_tooltip(f"Vype (keyboard) — {preferred}")
    except Exception as e:
        logger.error(f"Hotkey registration error: {e}", exc_info=True)
        print(f"Warning: Hotkey registration failed: {e}")

    logger.info("Application ready")
    print("\n✅ Vype ready! Press your hotkey to start dictating.\n")

    # Enter Tk mainloop to service settings/overlay UI
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        print(f"Error: {e}")
    finally:
        logger.info("Application shutting down")
        instance.release()


def main() -> None:
    args = _parse_args()
    if args.record_seconds is not None:
        _run_cli(args.record_seconds)
    else:
        _run_app()


if __name__ == "__main__":
    main()
