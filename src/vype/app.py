"""Composition root: wire config → pipeline → hotkey → UI, then run Qt."""

from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .cleanup import Cleaner
from .config import config_dir, config_path, load_config
from .history import History
from .hotkey import HotkeyListener
from .inject import Injector
from .pipeline import Pipeline
from .recorder import Recorder
from .stt import create_transcriber

logger = logging.getLogger(__name__)


class Bridge(QObject):
    """Marshals pipeline callbacks (worker threads) onto the Qt main thread."""

    state_changed = Signal(str)
    preview = Signal(str)
    error = Signal(str)


def main() -> int:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        # the frozen (installer) build has no console — log to a file instead
        log_path = config_dir() / "vype.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, mode="w", encoding="utf-8"))
    except Exception:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
    )

    # headless API server for the mobile PWA / Siri Shortcuts
    if "serve" in sys.argv[1:2]:
        from .server import run_serve

        return run_serve()

    # installer's GPU task: download CUDA runtime, then exit (no tray/hotkey)
    if "--setup-gpu" in sys.argv:
        from .ui.gpu_dialog import GpuSetupWindow

        setup_app = QApplication(sys.argv)
        window = GpuSetupWindow()
        window.show()
        return setup_app.exec()

    from .gpu_setup import activate_if_installed

    activate_if_installed()  # must run before onnxruntime is imported

    cfg = load_config()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # single instance guard — a second launch would double every hotkey event
    guard = QSharedMemory("vype-single-instance")
    if not guard.create(1):
        print("Vype is already running.")
        return 1

    transcriber = create_transcriber(cfg.stt)
    history = History(config_dir() / "history.jsonl")
    if cfg.clear_history_on_exit:
        history.clear()  # also wipe leftovers from a session that was force-killed
    pipeline = Pipeline(
        recorder=Recorder(sample_rate=cfg.audio.sample_rate, device_id=cfg.audio.device_id),
        transcriber=transcriber,
        cleaner=Cleaner(cfg.cleanup),
        injector=Injector(),
        history=history,
        config=cfg,
    )

    bridge = Bridge()
    pipeline.on_state = bridge.state_changed.emit
    pipeline.on_preview = bridge.preview.emit
    pipeline.on_error = bridge.error.emit

    # hotkey listener lives in a mutable slot so settings can rebind it
    listener_slot: dict = {"listener": None}

    def start_listener() -> None:
        listener_slot["listener"] = HotkeyListener(
            key=cfg.hotkey.key,
            on_press=pipeline.press,
            on_release=pipeline.release,
            on_escape=pipeline.escape,
        )
        listener_slot["listener"].start()

    def stop_listener() -> None:
        if listener_slot["listener"] is not None:
            listener_slot["listener"].stop()
            listener_slot["listener"] = None

    def _input_devices() -> list[tuple[int, str]]:
        import sounddevice as sd

        return [
            (i, d["name"])
            for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        ]

    def open_settings() -> None:
        from .ui.settings import SettingsDialog

        def apply() -> None:
            pipeline.apply_settings()
            pipeline.replace_cleaner(Cleaner(cfg.cleanup))
            pipeline.recorder.set_device(cfg.audio.device_id)
            logger.info("Settings saved — hotkey '%s'", cfg.hotkey.key)

        stop_listener()  # so pressing keys in the capture field can't start dictation
        try:
            dialog = SettingsDialog(cfg, _input_devices(), on_save=apply)
            dialog.exec()
        finally:
            start_listener()  # rebinds to the (possibly new) key

    if cfg.ui.show_pill:
        from .ui.caption import CaptionBubble
        from .ui.history_popup import HistoryPopup
        from .ui.pill import Pill

        popup = HistoryPopup(pipeline.history)
        pill = Pill(
            level_provider=lambda: pipeline.recorder.level,
            cleanup_enabled_provider=lambda: pipeline.cleanup_enabled,
            on_click=lambda: popup.show_above(*pill.anchor_point()),
            on_right_click=open_settings,
        )
        bridge.state_changed.connect(pill.set_state)

        if cfg.ui.live_preview:
            caption = CaptionBubble(
                at_caret=cfg.ui.preview_at_caret,
                fallback_anchor=lambda: pill.anchor_point(),
            )
            bridge.state_changed.connect(caption.set_state)
            bridge.preview.connect(caption.set_text)

    from .ui.tray import build_tray

    tray = build_tray(app, pipeline, pipeline.history, config_path(), on_settings=open_settings)
    bridge.error.connect(
        lambda msg: tray.showMessage("Vype", msg, QSystemTrayIcon.MessageIcon.Warning, 3000)
    )

    # warm the model so the first hotkey press is instant; the throwaway
    # transcribe pays the one-time CUDA kernel-init cost (~5 s) up front
    def _preload() -> None:
        try:
            import numpy as np

            transcriber.load()
            transcriber.transcribe(np.zeros(16000, dtype=np.float32))
            logger.info("Model warm")
        except Exception as exc:
            logger.error("Model preload failed: %s", exc, exc_info=True)
            pipeline.on_error(f"Model failed to load: {exc}")

    threading.Thread(target=_preload, daemon=True, name="vype-preload").start()

    start_listener()

    logger.info("Vype ready — hold '%s' to dictate", cfg.hotkey.key)
    try:
        return app.exec()
    finally:
        stop_listener()
        if cfg.clear_history_on_exit:
            history.clear()  # privacy first: transcripts live only for the session
        guard.detach()


if __name__ == "__main__":
    sys.exit(main())
