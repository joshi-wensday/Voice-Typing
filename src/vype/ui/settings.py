"""Settings dialog: a frameless dark card, opened by right-clicking the pill.

Hotkey capture uses the `keyboard` library itself, so captured names match what
HotkeyListener expects. Combos are supported: hold several keys (e.g. Ctrl+Alt)
and the combo is finalized when the first key is released.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
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

_W = 420
_BG = QColor(20, 20, 24, 250)

_STYLE = """
QLabel {
    color: #d4d4d8;
    font-size: 9pt;
    background: transparent;
}
QLabel#title { color: #fafafa; }
QLabel#subtitle { color: #6b6b74; font-size: 8pt; }
QLabel#section {
    color: #5eead4;
    font-size: 7pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#hint { color: #55555e; font-size: 8pt; }
QLabel#fieldlabel { color: #a1a1aa; }

QLineEdit, QComboBox, QSpinBox {
    color: #e4e4e7;
    background: #1d1d23;
    border: 1px solid #2a2a32;
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 9pt;
    selection-background-color: #2dd4bf;
    selection-color: #0f172a;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: #3a3a44; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #2dd4bf;
    background: #202028;
}
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6b6b74;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    color: #e4e4e7;
    background: #1d1d23;
    border: 1px solid #2a2a32;
    border-radius: 9px;
    padding: 4px;
    selection-background-color: rgba(45, 212, 191, 40);
    selection-color: #e4e4e7;
    outline: none;
}
QSpinBox::up-button, QSpinBox::down-button { width: 0; }

QCheckBox {
    color: #d4d4d8;
    font-size: 9pt;
    spacing: 10px;
    background: transparent;
    padding: 2px 0;
}
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 6px;
    border: 1px solid #3a3a44;
    background: #1d1d23;
}
QCheckBox::indicator:hover { border-color: #4a4a56; }
QCheckBox::indicator:checked { background: #2dd4bf; border: 1px solid #2dd4bf; }

QPushButton {
    color: #d4d4d8;
    background: #1d1d23;
    border: 1px solid #2a2a32;
    border-radius: 9px;
    padding: 8px 18px;
    font-size: 9pt;
}
QPushButton:hover { background: #26262e; border-color: #3a3a44; }
QPushButton#primary {
    color: #0d1420;
    background: #2dd4bf;
    border: none;
    font-weight: 600;
}
QPushButton#primary:hover { background: #5eead4; }
QPushButton#capture {
    background: #1d1d23;
    border: 1px dashed #3a3a44;
    color: #5eead4;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QPushButton#capture:hover { border-color: #2dd4bf; }
QPushButton#close {
    color: #6b6b74;
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 11pt;
    padding: 2px 10px;
}
QPushButton#close:hover { color: #e4e4e7; background: rgba(255,255,255,14); }

QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #34343e; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #45454f; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
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


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldlabel")
    return label


class SettingsDialog(QDialog):
    def __init__(
        self,
        cfg: Config,
        input_devices: list[tuple[int, str]],
        on_save: Callable[[], None],
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Vype Settings")
        self.setStyleSheet(_STYLE)
        self.setFixedWidth(_W)
        self._cfg = cfg
        self._on_save = on_save
        self._drag_offset = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 24)
        root.setSpacing(0)

        # ── Header (custom title bar: draggable, with close button) ──
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Settings")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        subtitle = QLabel("Changes apply immediately unless noted")
        subtitle.setObjectName("subtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()
        close = QPushButton("✕")
        close.setObjectName("close")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.reject)
        header.addWidget(close, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)
        root.addSpacing(18)

        # ── Sections ──
        def section(text: str) -> None:
            label = QLabel(text.upper())
            label.setObjectName("section")
            root.addWidget(label)
            root.addSpacing(8)

        def form() -> QFormLayout:
            f = QFormLayout()
            f.setVerticalSpacing(10)
            f.setHorizontalSpacing(20)
            f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            root.addLayout(f)
            return f

        section("Dictation")
        dictation = form()

        self._hotkey = HotkeyCaptureButton(cfg.hotkey.key)
        dictation.addRow(_field_label("Hotkey"), self._hotkey)

        self._tap_ms = QSpinBox()
        self._tap_ms.setRange(100, 1000)
        self._tap_ms.setSingleStep(50)
        self._tap_ms.setSuffix(" ms")
        self._tap_ms.setValue(cfg.hotkey.tap_threshold_ms)
        dictation.addRow(_field_label("Tap-to-lock threshold"), self._tap_ms)

        self._mic = QComboBox()
        self._mic.addItem("System default", None)
        for device_id, name in input_devices:
            self._mic.addItem(name, device_id)
            if cfg.audio.device_id == device_id:
                self._mic.setCurrentIndex(self._mic.count() - 1)
        dictation.addRow(_field_label("Microphone"), self._mic)

        self._backend = QComboBox()
        for backend in ("parakeet", "whisper", "openai"):
            self._backend.addItem(backend)
        self._backend.setCurrentText(cfg.stt.backend)
        self._backend.setToolTip("Applies after restarting Vype")
        dictation.addRow(_field_label("Engine ↻"), self._backend)

        root.addSpacing(18)
        section("Live caption")
        self._live_preview = QCheckBox("Show caption while recording")
        self._live_preview.setChecked(cfg.ui.live_preview)
        root.addWidget(self._live_preview)
        self._at_caret = QCheckBox("Caption follows the text cursor")
        self._at_caret.setChecked(cfg.ui.preview_at_caret)
        root.addWidget(self._at_caret)

        root.addSpacing(18)
        section("AI cleanup")
        self._cleanup = QCheckBox("Clean transcripts with an LLM")
        self._cleanup.setChecked(cfg.cleanup.enabled)
        root.addWidget(self._cleanup)
        root.addSpacing(8)

        cleanup_form = form()
        self._cleanup_url = QLineEdit(cfg.cleanup.base_url)
        cleanup_form.addRow(_field_label("Endpoint"), self._cleanup_url)
        self._cleanup_model = QLineEdit(cfg.cleanup.model)
        cleanup_form.addRow(_field_label("Model"), self._cleanup_model)
        self._cleanup_key = QLineEdit(cfg.cleanup.api_key or "")
        self._cleanup_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cleanup_key.setPlaceholderText("optional")
        cleanup_form.addRow(_field_label("API key"), self._cleanup_key)

        root.addSpacing(16)
        hint = QLabel("Hold the hotkey to talk  ·  tap to lock hands-free  ·  Esc cancels")
        hint.setObjectName("hint")
        root.addWidget(hint)
        root.addSpacing(14)

        # ── Buttons ──
        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        button_row.addWidget(cancel)
        button_row.addSpacing(8)
        button_row.addWidget(save)
        root.addLayout(button_row)

    # ── Frameless chrome ──────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(58, 58, 68))
        p.setBrush(_BG)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 16, 16)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None

    # ── Persistence ───────────────────────────────────────────────────────────

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
