"""History popup: click the pill → this session's dictations.

Interaction design:
- scrollable list (newest first), slim modern scrollbar
- hovering a row expands it by the golden ratio (animated) and highlights it,
  revealing more of the text
- click a row → copies it, the row blinks teal, popup closes
- a delete button on the right of each row removes that record
- storage is session-only (wiped on app exit) — privacy first
"""

from __future__ import annotations

import time

from PySide6.QtCore import (
    QEasingCurve,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_W = 400
_MAX_LIST_H = 380
_ROW_H = 52
_ROW_H_EXPANDED = int(_ROW_H * 1.618)  # golden ratio
_BG = QColor(20, 20, 24, 248)

_SCROLL_STYLE = """
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #34343e;
    border-radius: 3px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #45454f; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

_ROW_BASE = """
QFrame#row {{
    background: {bg};
    border: 1px solid {border};
    border-radius: 10px;
}}
"""

_DELETE_STYLE = """
QPushButton {
    color: #6b6b74;
    background: transparent;
    border: none;
    border-radius: 6px;
    font-size: 11pt;
    padding: 2px 6px;
}
QPushButton:hover { color: #f87171; background: rgba(248,113,113,26); }
"""


def _age(ts: float) -> str:
    s = max(0, int(time.time() - ts))
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    return f"{s // 3600}h ago"


class HistoryRow(QFrame):
    def __init__(self, record: dict, on_copy, on_delete) -> None:
        super().__init__()
        self.setObjectName("row")
        self._text = record.get("cleaned") or record.get("raw") or ""
        self._on_copy = on_copy
        self._on_delete = on_delete
        self._ts = record.get("ts", 0.0)
        self._blinking = False

        self.setFixedHeight(_ROW_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_row_style(hover=False)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 6, 8)
        row.setSpacing(6)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self._label = QLabel(self._text)
        self._label.setWordWrap(True)
        self._label.setFont(QFont("Segoe UI", 9))
        self._label.setStyleSheet("color: #e4e4e7; background: transparent; border: none;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        text_col.addWidget(self._label, stretch=1)

        self._meta = QLabel(_age(self._ts))
        self._meta.setFont(QFont("Segoe UI", 7))
        self._meta.setStyleSheet("color: #6b6b74; background: transparent; border: none;")
        text_col.addWidget(self._meta)

        row.addLayout(text_col, stretch=1)

        delete = QPushButton("✕")
        delete.setStyleSheet(_DELETE_STYLE)
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.setFixedSize(26, 26)
        delete.setToolTip("Delete this transcript")
        delete.clicked.connect(lambda: self._on_delete(self._ts))
        row.addWidget(delete, alignment=Qt.AlignmentFlag.AlignTop)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.setFixedHeight(int(v)))

    # ── Style helpers ─────────────────────────────────────────────────────────

    def _set_row_style(self, hover: bool, blink: bool = False) -> None:
        if blink:
            bg, border = "rgba(45,212,191,64)", "#2dd4bf"
        elif hover:
            bg, border = "rgba(255,255,255,16)", "#3a3a44"
        else:
            bg, border = "rgba(255,255,255,7)", "transparent"
        self.setStyleSheet(_ROW_BASE.format(bg=bg, border=border))

    def _animate_height(self, target: int) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.height())
        self._anim.setEndValue(target)
        self._anim.start()

    def _expanded_height(self) -> int:
        """Height needed to show the full text, or _ROW_H if it already fits.

        Expansion is only warranted when the collapsed row actually cuts the
        text off — measured against the label's real laid-out width.
        """
        from PySide6.QtGui import QFontMetrics

        metrics = QFontMetrics(self._label.font())
        needed = metrics.boundingRect(
            0, 0, max(self._label.width(), 1), 10_000,
            Qt.TextFlag.TextWordWrap, self._text,
        ).height()
        if needed <= self._label.height() + 2:
            return _ROW_H  # fully visible already — no expansion
        chrome = _ROW_H - self._label.height()  # margins + meta line
        return min(_ROW_H_EXPANDED, needed + chrome)

    # ── Events ────────────────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        if not self._blinking:
            self._set_row_style(hover=True)
            target = self._expanded_height()
            if target > _ROW_H:
                self._animate_height(target)

    def leaveEvent(self, event) -> None:
        if not self._blinking:
            self._set_row_style(hover=False)
            if self.height() != _ROW_H:
                self._animate_height(_ROW_H)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._blinking:
            QApplication.clipboard().setText(self._text)
            self._blink_then(lambda: self._on_copy())

    def _blink_then(self, done) -> None:
        """Two quick teal flashes to confirm the copy, then notify."""
        self._blinking = True
        steps = [
            (0, lambda: self._set_row_style(hover=False, blink=True)),
            (110, lambda: self._set_row_style(hover=False)),
            (220, lambda: self._set_row_style(hover=False, blink=True)),
            (380, done),
        ]
        for delay, fn in steps:
            QTimer.singleShot(delay, fn)


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

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 6, 10)
        root.setSpacing(8)

        header = QLabel("This session")
        header.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        header.setStyleSheet(
            "color: #6b6b74; background: transparent; letter-spacing: 1px; padding-left: 2px;"
        )
        root.addWidget(header)

        self._scroll = QScrollArea()
        self._scroll.setStyleSheet(_SCROLL_STYLE)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._scroll)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._list = QVBoxLayout(self._container)
        self._list.setContentsMargins(0, 0, 4, 0)
        self._list.setSpacing(6)
        self._list.addStretch()
        self._scroll.setWidget(self._container)

    def show_above(self, anchor_x: int, anchor_bottom_y: int) -> None:
        self._rebuild()
        screen = QApplication.primaryScreen().availableGeometry()
        x = min(max(anchor_x - _W // 2, screen.left() + 4), screen.right() - _W - 4)
        y = max(anchor_bottom_y - self.height() - 8, screen.top() + 4)
        self.move(x, y)
        self.show()

    def _rebuild(self) -> None:
        while self._list.count() > 1:  # keep the trailing stretch
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        records = self._history.recent(30)
        if not records:
            empty = QLabel("Nothing dictated this session")
            empty.setFont(QFont("Segoe UI", 9))
            empty.setStyleSheet("color: #6b6b74; background: transparent; padding: 8px;")
            self._list.insertWidget(0, empty)
            list_h = 60
        else:
            for i, record in enumerate(records):
                row = HistoryRow(record, on_copy=self.hide, on_delete=self._delete)
                self._list.insertWidget(i, row)
            list_h = min(_MAX_LIST_H, len(records) * (_ROW_H + 6) + 8)

        self._scroll.setFixedHeight(list_h)
        self.setFixedHeight(list_h + 44)

    def _delete(self, ts: float) -> None:
        self._history.delete(ts)
        anchor_bottom = self.geometry().bottom() + 8
        anchor_x = self.geometry().center().x()
        self.show_above(anchor_x, anchor_bottom)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(58, 58, 68))
        p.setBrush(_BG)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
