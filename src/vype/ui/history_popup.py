"""History popup: click the pill → recent dictations, click one to copy it."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_W = 420
_BG = QColor(24, 24, 28, 245)

_ITEM_STYLE = """
QPushButton {
    color: rgb(228,228,231);
    background: rgba(255,255,255,12);
    border: none;
    border-radius: 8px;
    padding: 8px 10px;
    text-align: left;
}
QPushButton:hover { background: rgba(94,234,212,40); }
"""


def _age(ts: float) -> str:
    s = max(0, int(time.time() - ts))
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


class HistoryPopup(QWidget):
    def __init__(self, history) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Popup,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._history = history
        self.setFixedWidth(_W)

    def show_above(self, anchor_x: int, anchor_bottom_y: int) -> None:
        self._rebuild()
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        x = min(max(anchor_x - _W // 2, screen.left() + 4), screen.right() - _W - 4)
        y = max(anchor_bottom_y - self.height() - 8, screen.top() + 4)
        self.move(x, y)
        self.show()

    def _rebuild(self) -> None:
        if self.layout() is not None:
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            layout = self.layout()
        else:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(6)

        records = self._history.recent(8)
        if not records:
            empty = QLabel("No dictations yet")
            empty.setStyleSheet("color: rgb(161,161,170); background: transparent;")
            empty.setFont(QFont("Segoe UI", 9))
            layout.addWidget(empty)
            return

        for record in records:
            text = record.get("cleaned") or record.get("raw") or ""
            preview = text if len(text) <= 90 else text[:87] + "…"
            button = QPushButton(f"{preview}\n{_age(record.get('ts', 0))}")
            button.setStyleSheet(_ITEM_STYLE)
            button.setFont(QFont("Segoe UI", 9))
            button.setCursor(Qt.CursorShape.PointingHandCursor)

            def copy_and_close(checked=False, t=text):
                QApplication.clipboard().setText(t)
                self.hide()

            button.clicked.connect(copy_and_close)
            layout.addWidget(button)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BG)
        p.drawRoundedRect(self.rect(), 12, 12)
