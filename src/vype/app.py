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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # single instance guard — a second launch would double every hotkey event
    guard = QSharedMemory("vype-single-instance")
    if not guard.create(1):
        print("Vype is already running.")
        return 1

    transcriber = create_transcriber(cfg.stt)
    pipeline = Pipeline(
        recorder=Recorder(sample_rate=cfg.audio.sample_rate, device_id=cfg.audio.device_id),
        transcriber=transcriber,
        cleaner=Cleaner(cfg.cleanup),
        injector=Injector(),
        history=History(config_dir() / "history.jsonl"),
        config=cfg,
    )

    bridge = Bridge()
    pipeline.on_state = bridge.state_changed.emit
    pipeline.on_preview = bridge.preview.emit
    pipeline.on_error = bridge.error.emit

    if cfg.ui.show_pill:
        from .ui.caption import CaptionBubble
        from .ui.history_popup import HistoryPopup
        from .ui.pill import Pill

        popup = HistoryPopup(pipeline.history)
        pill = Pill(
            level_provider=lambda: pipeline.recorder.level,
            cleanup_enabled_provider=lambda: pipeline.cleanup_enabled,
            on_click=lambda: popup.show_above(*pill.anchor_point()),
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

    tray = build_tray(app, pipeline, pipeline.history, config_path())
    bridge.error.connect(
        lambda msg: tray.showMessage("Vype", msg, QSystemTrayIcon.MessageIcon.Warning, 3000)
    )

    # warm the model so the first hotkey press is instant; the throwaway
    # transcribe pays the one-time CUDA kernel-init cost (~5 s) up front
    def _preload() -> None:
        import numpy as np

        transcriber.load()
        transcriber.transcribe(np.zeros(16000, dtype=np.float32))
        logger.info("Model warm")

    threading.Thread(target=_preload, daemon=True, name="vype-preload").start()

    listener = HotkeyListener(
        key=cfg.hotkey.key,
        on_press=pipeline.press,
        on_release=pipeline.release,
        on_escape=pipeline.escape,
    )
    listener.start()

    logger.info("Vype ready — hold '%s' to dictate", cfg.hotkey.key)
    try:
        return app.exec()
    finally:
        listener.stop()
        guard.detach()


if __name__ == "__main__":
    sys.exit(main())
