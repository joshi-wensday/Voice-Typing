"""Live-preview caption: a small bubble that follows the text caret while recording."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .caret import preview_anchor_point

_MAX_W = 440
_BG = QColor(24, 24, 28, 235)
_TEXT = QColor(228, 228, 231)


class CaptionBubble(QWidget):
    def __init__(self, at_caret: bool = True, fallback_anchor=None) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._at_caret = at_caret
        self._fallback_anchor = fallback_anchor  # () -> (x, y), e.g. above the pill

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setFont(QFont("Segoe UI", 10))
        self._label.setStyleSheet("color: rgb(228,228,231); background: transparent;")
        self._label.setMaximumWidth(_MAX_W - 24)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._label)

        self._recording = False
        self.hide()

    @Slot(str)
    def set_state(self, state: str) -> None:
        self._recording = state in ("recording", "recording-locked")
        if not self._recording:
            self._label.setText("")
            self.hide()

    @Slot(str)
    def set_text(self, text: str) -> None:
        if not self._recording or not text:
            return
        # show the tail — the words just spoken — capped to ~3 lines
        self._label.setText(text[-220:])
        self.adjustSize()
        self._reposition()
        self.show()

    def _reposition(self) -> None:
        anchor = preview_anchor_point() if self._at_caret else None
        if anchor is None and self._fallback_anchor is not None:
            anchor = self._fallback_anchor()
        if anchor is None:
            return
        x, y = anchor
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        # below the caret; flip above if there's no room
        px = min(max(x - 16, screen.left() + 4), screen.right() - w - 4)
        py = y + 14
        if py + h > screen.bottom() - 4:
            py = y - h - 28
        self.move(px, max(py, screen.top() + 4))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BG)
        p.drawRoundedRect(self.rect(), 10, 10)
