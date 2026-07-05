"""The pill: a small always-on-top status strip at the bottom-center of the screen.

Idle       — thin, dim, nearly invisible
Recording  — audio-level bars + live caption of what you've said so far + timer
Processing — pulsing dot
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QApplication, QWidget

_BAR_COUNT = 24
_PILL_W, _PILL_H = 320, 36
_CAPTION_H = 52

_BG = QColor(24, 24, 28, 235)
_BG_IDLE = QColor(24, 24, 28, 90)
_ACCENT = QColor(94, 234, 212)  # teal
_PROCESSING = QColor(250, 204, 21)  # amber
_TEXT = QColor(228, 228, 231)
_TEXT_DIM = QColor(161, 161, 170)


class Pill(QWidget):
    def __init__(self, level_provider, cleanup_enabled_provider=None) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._level_provider = level_provider
        self._cleanup_enabled = cleanup_enabled_provider or (lambda: False)
        self._state = "idle"
        self._preview = ""
        self._levels = [0.0] * _BAR_COUNT
        self._record_started = 0.0
        self._pulse = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

        self._reposition()
        self.show()

    # ── Slots (connected to pipeline bridge signals, queued across threads) ──

    @Slot(str)
    def set_state(self, state: str) -> None:
        self._state = state
        if state == "recording":
            self._record_started = time.monotonic()
            self._levels = [0.0] * _BAR_COUNT
        if state != "recording":
            self._preview = ""
        self._reposition()
        self.update()

    @Slot(str)
    def set_preview(self, text: str) -> None:
        self._preview = text
        self.update()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self._state == "recording":
            self._levels.pop(0)
            self._levels.append(float(self._level_provider()))
            self.update()
        elif self._state == "processing":
            self._pulse = (self._pulse + 0.08) % 1.0
            self.update()

    def _reposition(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        show_caption = self._state == "recording"
        h = _PILL_H + (_CAPTION_H if show_caption else 0)
        self.setFixedSize(_PILL_W, h)
        self.move(
            screen.center().x() - _PILL_W // 2,
            screen.bottom() - h - 12,
        )

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pill_top = self.height() - _PILL_H

        # caption (recording only)
        if self._state == "recording" and self._preview:
            p.setBrush(_BG)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 0, _PILL_W, _CAPTION_H - 6, 10, 10)
            p.setPen(_TEXT)
            font = QFont("Segoe UI", 9)
            p.setFont(font)
            metrics = QFontMetrics(font)
            # show the tail of the preview — the words just spoken
            text = metrics.elidedText(
                self._preview, Qt.TextElideMode.ElideLeft, (_PILL_W - 24) * 2
            )
            p.drawText(
                self.rect().adjusted(12, 6, -12, -(_PILL_H + 12)),
                Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignBottom,
                text,
            )

        # pill body
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BG if self._state != "idle" else _BG_IDLE)
        p.drawRoundedRect(0, pill_top, _PILL_W, _PILL_H, _PILL_H // 2, _PILL_H // 2)

        if self._state == "recording":
            self._paint_bars(p, pill_top)
        elif self._state == "processing":
            self._paint_processing(p, pill_top)
        else:
            self._paint_idle(p, pill_top)

        # cleanup-mode dot
        if self._cleanup_enabled():
            p.setBrush(_ACCENT)
            p.drawEllipse(_PILL_W - 16, pill_top + _PILL_H // 2 - 3, 6, 6)

    def _paint_bars(self, p: QPainter, top: int) -> None:
        bar_w = 5
        gap = 3
        total = _BAR_COUNT * (bar_w + gap) - gap
        x0 = (_PILL_W - total) // 2 - 20
        cy = top + _PILL_H // 2
        p.setBrush(_ACCENT)
        for i, level in enumerate(self._levels):
            h = max(3, int(level * (_PILL_H - 12)))
            p.drawRoundedRect(x0 + i * (bar_w + gap), cy - h // 2, bar_w, h, 2, 2)
        # elapsed timer
        elapsed = int(time.monotonic() - self._record_started)
        p.setPen(_TEXT_DIM)
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(
            self.rect().adjusted(0, top, -14, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{elapsed // 60}:{elapsed % 60:02d}",
        )

    def _paint_processing(self, p: QPainter, top: int) -> None:
        cy = top + _PILL_H // 2
        p.setBrush(_PROCESSING)
        import math

        for i in range(3):
            phase = (self._pulse + i / 3.0) % 1.0
            r = 3 + 2 * abs(math.sin(phase * math.pi))
            p.drawEllipse(
                int(_PILL_W / 2 - 20 + i * 16 - r), int(cy - r), int(2 * r), int(2 * r)
            )

    def _paint_idle(self, p: QPainter, top: int) -> None:
        p.setPen(_TEXT_DIM)
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(
            self.rect().adjusted(0, top, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "hold to talk",
        )
