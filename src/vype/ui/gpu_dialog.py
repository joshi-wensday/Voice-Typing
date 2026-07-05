"""Progress window for `vype.exe --setup-gpu` (run by the installer's GPU task)."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .. import gpu_setup

_BG = QColor(20, 20, 24, 250)

_STYLE = """
QLabel { color: #d4d4d8; font-size: 9pt; background: transparent; }
QLabel#title { color: #fafafa; }
QLabel#status { color: #a1a1aa; font-size: 8pt; }
QProgressBar {
    background: #1d1d23;
    border: 1px solid #2a2a32;
    border-radius: 7px;
    height: 14px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background: #2dd4bf; border-radius: 6px; }
QPushButton {
    color: #0d1420;
    background: #2dd4bf;
    border: none;
    border-radius: 9px;
    padding: 8px 22px;
    font-size: 9pt;
    font-weight: 600;
}
QPushButton:hover { background: #5eead4; }
QPushButton:disabled { background: #26262e; color: #6b6b74; }
"""


class _Bridge(QObject):
    progress = Signal(str, float)
    failed = Signal(str)
    done = Signal()


class GpuSetupWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(_STYLE)
        self.setFixedSize(440, 170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)

        title = QLabel("Setting up GPU acceleration")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        layout.addWidget(title)

        self._status = QLabel("Preparing… (~1.5 GB download from PyPI)")
        self._status.setObjectName("status")
        layout.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        layout.addWidget(self._bar)

        self._button = QPushButton("Close")
        self._button.setEnabled(False)
        self._button.clicked.connect(self.close)
        layout.addWidget(self._button, alignment=Qt.AlignmentFlag.AlignRight)

        self._bridge = _Bridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.failed.connect(self._on_failed)
        self._bridge.done.connect(self._on_done)

        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            gpu_setup.install(lambda text, frac: self._bridge.progress.emit(text, frac))
            self._bridge.done.emit()
        except Exception as exc:
            self._bridge.failed.emit(str(exc))

    def _on_progress(self, text: str, frac: float) -> None:
        self._status.setText(text)
        self._bar.setValue(int(frac * 1000))

    def _on_done(self) -> None:
        self._status.setText("Done — Vype will use your NVIDIA GPU from the next launch.")
        self._bar.setValue(1000)
        self._button.setEnabled(True)

    def _on_failed(self, message: str) -> None:
        self._status.setText(f"Failed: {message}\nGPU is optional — Vype still works on CPU.")
        self._status.setWordWrap(True)
        self._button.setEnabled(True)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(58, 58, 68))
        p.setBrush(_BG)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 16, 16)
