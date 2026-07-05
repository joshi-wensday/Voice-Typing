"""System tray icon: cleanup toggle, copy-last, open config, quit."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def _icon_path() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller: datas land in _MEIPASS
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "logo-1280.ico"
    return Path(__file__).resolve().parents[3] / "logo-1280.ico"


_ICON_PATH = _icon_path()


def build_tray(app, pipeline, history, config_file: Path, on_settings=None) -> QSystemTrayIcon:
    icon = QIcon(str(_ICON_PATH)) if _ICON_PATH.exists() else QIcon()
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Vype — hold your hotkey to dictate")

    menu = QMenu()

    cleanup_action = QAction("AI cleanup mode", menu)
    cleanup_action.setCheckable(True)
    cleanup_action.setChecked(pipeline.cleanup_enabled)

    def toggle_cleanup(checked: bool) -> None:
        pipeline.cleanup_enabled = checked

    cleanup_action.toggled.connect(toggle_cleanup)
    menu.addAction(cleanup_action)

    copy_action = QAction("Copy last transcript", menu)

    def copy_last() -> None:
        text = history.last_text()
        if text:
            QApplication.clipboard().setText(text)

    copy_action.triggered.connect(copy_last)
    menu.addAction(copy_action)

    menu.addSeparator()

    if on_settings is not None:
        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(on_settings)
        menu.addAction(settings_action)

    config_action = QAction("Open config file", menu)
    config_action.triggered.connect(lambda: os.startfile(config_file))
    menu.addAction(config_action)

    menu.addSeparator()

    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.show()
    return tray
