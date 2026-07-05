"""Settings dialog: one compact modal, opened by right-clicking the pill.

Hotkey capture uses the `keyboard` library itself, so the captured key name
("right ctrl", "f8", …) is exactly what the HotkeyListener expects.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from ..config import Config, save_config

_STYLE = """
QDialog { background: rgb(28, 28, 32); }
QLabel { color: rgb(228, 228, 231); }
QLineEdit, QComboBox, QSpinBox {
    color: rgb(228, 228, 231);
    background: rgba(255, 255, 255, 14);
    border: 1px solid rgba(255, 255, 255, 25);
    border-radius: 6px;
    padding: 4px 8px;
}
QCheckBox { color: rgb(228, 228, 231); }
QPushButton {
    color: rgb(228, 228, 231);
    background: rgba(255, 255, 255, 18);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 6px;
    padding: 5px 14px;
}
QPushButton:hover { background: rgba(94, 234, 212, 50); }
"""


class HotkeyCaptureButton(QPushButton):
    """Shows the current key; click, then press any key to rebind."""

    captured = Signal(str)

    def __init__(self, current: str) -> None:
        super().__init__(current)
        self.key = current
        self._hook = None
        self.clicked.connect(self._begin_capture)
        self.captured.connect(self._apply)

    def _begin_capture(self) -> None:
        if self._hook is not None:
            return
        self.setText("press a key…")
        import keyboard

        def on_event(event) -> None:
            if event.event_type == "down" and event.name:
                self._end_capture()
                self.captured.emit(event.name)

        self._hook = keyboard.hook(on_event)

    def _end_capture(self) -> None:
        if self._hook is not None:
            import keyboard

            try:
                keyboard.unhook(self._hook)
            except Exception:
                pass
            self._hook = None

    def _apply(self, name: str) -> None:
        self.key = name
        self.setText(name)

    def closeEvent(self, event) -> None:  # safety: never leak the hook
        self._end_capture()
        super().closeEvent(event)


class SettingsDialog(QDialog):
    def __init__(
        self,
        cfg: Config,
        input_devices: list[tuple[int, str]],
        on_save: Callable[[], None],
    ) -> None:
        super().__init__(None, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Vype Settings")
        self.setStyleSheet(_STYLE)
        self._cfg = cfg
        self._on_save = on_save

        form = QFormLayout(self)
        form.setVerticalSpacing(10)

        # Hotkey
        self._hotkey = HotkeyCaptureButton(cfg.hotkey.key)
        form.addRow("Hotkey (hold=talk, tap=lock)", self._hotkey)

        self._tap_ms = QSpinBox()
        self._tap_ms.setRange(100, 1000)
        self._tap_ms.setSingleStep(50)
        self._tap_ms.setSuffix(" ms")
        self._tap_ms.setValue(cfg.hotkey.tap_threshold_ms)
        form.addRow("Tap threshold", self._tap_ms)

        # Microphone
        self._mic = QComboBox()
        self._mic.addItem("System default", None)
        for device_id, name in input_devices:
            self._mic.addItem(name, device_id)
            if cfg.audio.device_id == device_id:
                self._mic.setCurrentIndex(self._mic.count() - 1)
        form.addRow("Microphone", self._mic)

        # STT
        self._backend = QComboBox()
        for backend in ("parakeet", "whisper", "openai"):
            self._backend.addItem(backend)
        self._backend.setCurrentText(cfg.stt.backend)
        form.addRow("STT engine (restart to apply)", self._backend)

        # Preview
        self._live_preview = QCheckBox("Show live caption while recording")
        self._live_preview.setChecked(cfg.ui.live_preview)
        form.addRow(self._live_preview)

        self._at_caret = QCheckBox("Caption follows the text cursor")
        self._at_caret.setChecked(cfg.ui.preview_at_caret)
        form.addRow(self._at_caret)

        # Cleanup
        self._cleanup = QCheckBox("AI cleanup mode")
        self._cleanup.setChecked(cfg.cleanup.enabled)
        form.addRow(self._cleanup)

        self._cleanup_url = QLineEdit(cfg.cleanup.base_url)
        form.addRow("Cleanup endpoint", self._cleanup_url)

        self._cleanup_model = QLineEdit(cfg.cleanup.model)
        form.addRow("Cleanup model", self._cleanup_model)

        self._cleanup_key = QLineEdit(cfg.cleanup.api_key or "")
        self._cleanup_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cleanup_key.setPlaceholderText("optional")
        form.addRow("Cleanup API key", self._cleanup_key)

        hint = QLabel("Config file: ~/.vype/config.yaml")
        hint.setStyleSheet("color: rgb(140,140,148); font-size: 8pt;")
        form.addRow(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self) -> None:
        cfg = self._cfg
        cfg.hotkey.key = self._hotkey.key
        cfg.hotkey.tap_threshold_ms = self._tap_ms.value()
        cfg.audio.device_id = self._mic.currentData()
        cfg.stt.backend = self._backend.currentText()
        cfg.ui.live_preview = self._live_preview.isChecked()
        cfg.ui.preview_at_caret = self._at_caret.isChecked()
        cfg.cleanup.enabled = self._cleanup.isChecked()
        cfg.cleanup.base_url = self._cleanup_url.text().strip()
        cfg.cleanup.model = self._cleanup_model.text().strip()
        cfg.cleanup.api_key = self._cleanup_key.text().strip() or None
        save_config(cfg)
        self._on_save()
        self.accept()

    def reject(self) -> None:
        self._hotkey._end_capture()
        super().reject()
