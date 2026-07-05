"""Settings dialog: one compact modal, opened by right-clicking the pill.

Hotkey capture uses the `keyboard` library itself, so captured names match what
HotkeyListener expects. Combos are supported: hold several keys (e.g. Ctrl+Alt)
and the combo is finalized when the first key is released.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import Config, save_config

_STYLE = """
QDialog {
    background: #141418;
}
QLabel {
    color: #d4d4d8;
    font-size: 9pt;
    background: transparent;
}
QLabel#section {
    color: #6b6b74;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 1px;
    padding-top: 6px;
}
QLabel#hint {
    color: #55555e;
    font-size: 8pt;
}
QLineEdit, QComboBox, QSpinBox {
    color: #e4e4e7;
    background: #1e1e24;
    border: 1px solid #2a2a32;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 9pt;
    selection-background-color: #2dd4bf;
    selection-color: #0f172a;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #2dd4bf;
    background: #212129;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6b6b74;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    color: #e4e4e7;
    background: #1e1e24;
    border: 1px solid #2a2a32;
    border-radius: 8px;
    selection-background-color: #164e63;
}
QSpinBox::up-button, QSpinBox::down-button { width: 0; }
QCheckBox {
    color: #d4d4d8;
    font-size: 9pt;
    spacing: 9px;
    background: transparent;
}
QCheckBox::indicator {
    width: 17px; height: 17px;
    border-radius: 5px;
    border: 1px solid #3a3a44;
    background: #1e1e24;
}
QCheckBox::indicator:checked {
    background: #2dd4bf;
    border: 1px solid #2dd4bf;
    image: url(none);
}
QPushButton {
    color: #d4d4d8;
    background: #1e1e24;
    border: 1px solid #2a2a32;
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 9pt;
}
QPushButton:hover { background: #26262e; border-color: #3a3a44; }
QPushButton#primary {
    color: #0f172a;
    background: #2dd4bf;
    border: none;
    font-weight: 600;
}
QPushButton#primary:hover { background: #5eead4; }
QPushButton#capture {
    background: #1e1e24;
    border: 1px dashed #3a3a44;
    color: #2dd4bf;
    font-weight: 600;
}
QPushButton#capture:hover { border-color: #2dd4bf; }
"""


class HotkeyCaptureButton(QPushButton):
    """Shows the current hotkey; click, then press a key or chord to rebind.

    Keys held simultaneously accumulate into a combo; the first key-up
    finalizes it (press Ctrl and Alt together → "ctrl+alt").
    """

    captured = Signal(str)

    def __init__(self, current: str) -> None:
        super().__init__(current)
        self.setObjectName("capture")
        self.key = current
        self._hook = None
        self._held: list[str] = []
        self.clicked.connect(self._begin_capture)
        self.captured.connect(self._apply)

    def _begin_capture(self) -> None:
        if self._hook is not None:
            return
        self.setText("press a key or chord…")
        self._held = []
        import keyboard

        def canonical(name: str) -> str:
            for prefix in ("left ", "right "):
                if name.startswith(prefix):
                    return name.removeprefix(prefix)
            return "alt" if name == "alt gr" else name

        def on_event(event) -> None:
            if not event.name:
                return
            if event.event_type == "down":
                name = canonical(event.name.lower())
                if name not in self._held:
                    self._held.append(name)
            elif self._held:  # first key-up finalizes the combo
                self._end_capture()
                self.captured.emit("+".join(self._held))

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


def _section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("section")
    return label


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
        self.setFixedWidth(400)
        self._cfg = cfg
        self._on_save = on_save

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        root.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(16)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        root.addLayout(form)

        # ── Dictation ──
        form.addRow(_section("Dictation"))

        self._hotkey = HotkeyCaptureButton(cfg.hotkey.key)
        form.addRow("Hotkey", self._hotkey)

        self._tap_ms = QSpinBox()
        self._tap_ms.setRange(100, 1000)
        self._tap_ms.setSingleStep(50)
        self._tap_ms.setSuffix(" ms")
        self._tap_ms.setValue(cfg.hotkey.tap_threshold_ms)
        form.addRow("Tap-to-lock threshold", self._tap_ms)

        self._mic = QComboBox()
        self._mic.addItem("System default", None)
        for device_id, name in input_devices:
            self._mic.addItem(name, device_id)
            if cfg.audio.device_id == device_id:
                self._mic.setCurrentIndex(self._mic.count() - 1)
        form.addRow("Microphone", self._mic)

        self._backend = QComboBox()
        for backend in ("parakeet", "whisper", "openai"):
            self._backend.addItem(backend)
        self._backend.setCurrentText(cfg.stt.backend)
        form.addRow("Engine  (restart to apply)", self._backend)

        # ── Live caption ──
        form.addRow(_section("Live caption"))

        self._live_preview = QCheckBox("Show caption while recording")
        self._live_preview.setChecked(cfg.ui.live_preview)
        form.addRow(self._live_preview)

        self._at_caret = QCheckBox("Caption follows the text cursor")
        self._at_caret.setChecked(cfg.ui.preview_at_caret)
        form.addRow(self._at_caret)

        # ── AI cleanup ──
        form.addRow(_section("AI cleanup"))

        self._cleanup = QCheckBox("Clean transcripts with an LLM")
        self._cleanup.setChecked(cfg.cleanup.enabled)
        form.addRow(self._cleanup)

        self._cleanup_url = QLineEdit(cfg.cleanup.base_url)
        form.addRow("Endpoint", self._cleanup_url)

        self._cleanup_model = QLineEdit(cfg.cleanup.model)
        form.addRow("Model", self._cleanup_model)

        self._cleanup_key = QLineEdit(cfg.cleanup.api_key or "")
        self._cleanup_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cleanup_key.setPlaceholderText("optional")
        form.addRow("API key", self._cleanup_key)

        hint = QLabel("Hold the hotkey to talk · tap it to lock hands-free · Esc cancels")
        hint.setObjectName("hint")
        root.addSpacing(4)
        root.addWidget(hint)

        # ── Buttons ──
        buttons = QWidget()
        button_row = QHBoxLayout(buttons)
        button_row.setContentsMargins(0, 8, 0, 0)
        button_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        root.addWidget(buttons)

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
