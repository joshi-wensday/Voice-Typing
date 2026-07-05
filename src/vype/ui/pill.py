"""The pill: a small dot at the bottom-center that expands into a waveform while
you speak.

Idle              — small dim circle; click → history popup
Recording         — widens into a pill with a live symmetric waveform + timer
Recording locked  — same, plus a lock glyph (hands-free mode)
Processing        — compact pill with pulsing dots
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QWidget

_BAR_COUNT = 36
_DOT = 22          # idle: small circle
_WIDE_W, _H = 320, 36
_PROC_W = 120
_MARGIN_BOTTOM = 14

_BG = QColor(24, 24, 28, 235)
_BG_IDLE = QColor(24, 24, 28, 150)
_ACCENT = QColor(94, 234, 212)   # teal
_PROCESSING = QColor(250, 204, 21)  # amber
_TEXT_DIM = QColor(161, 161, 170)


class Pill(QWidget):
    def __init__(self, level_provider, cleanup_enabled_provider=None, on_click=None) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._level_provider = level_provider
        self._cleanup_enabled = cleanup_enabled_provider or (lambda: False)
        self._on_click = on_click

        self._state = "idle"
        self._levels = [0.0] * _BAR_COUNT
        self._record_started = 0.0
        self._pulse = 0.0

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

        self.setGeometry(self._target_rect())
        self.show()

    # ── Slots ─────────────────────────────────────────────────────────────────

    @Slot(str)
    def set_state(self, state: str) -> None:
        was_recording = self._is_recording()
        self._state = state
        if self._is_recording() and not was_recording:
            self._record_started = time.monotonic()
            self._levels = [0.0] * _BAR_COUNT
        self._animate_to(self._target_rect())
        self.update()

    def anchor_point(self) -> tuple[int, int]:
        """Top-center of the pill, for anchoring popups."""
        g = self.geometry()
        return g.center().x(), g.top()

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _is_recording(self) -> bool:
        return self._state in ("recording", "recording-locked")

    def _target_rect(self) -> QRect:
        screen = QApplication.primaryScreen().availableGeometry()
        if self._is_recording():
            w, h = _WIDE_W, _H
        elif self._state == "processing":
            w, h = _PROC_W, _H
        else:
            w, h = _DOT, _DOT
        return QRect(
            screen.center().x() - w // 2,
            screen.bottom() - h - _MARGIN_BOTTOM,
            w,
            h,
        )

    def _animate_to(self, rect: QRect) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(rect)
        self._anim.start()

    # ── Animation tick ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self._is_recording():
            self._levels.pop(0)
            self._levels.append(float(self._level_provider()))
            self.update()
        elif self._state == "processing":
            self._pulse = (self._pulse + 0.08) % 1.0
            self.update()

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        radius = min(self.height(), _H) // 2
        p.setBrush(_BG if self._state != "idle" else _BG_IDLE)
        p.drawRoundedRect(self.rect(), radius, radius)

        if self._is_recording():
            self._paint_waveform(p)
        elif self._state == "processing":
            self._paint_processing(p)
        else:
            self._paint_idle_dot(p)

    def _paint_idle_dot(self, p: QPainter) -> None:
        cx, cy = self.width() / 2, self.height() / 2
        color = _ACCENT if self._cleanup_enabled() else _TEXT_DIM
        p.setBrush(color)
        r = 4
        p.drawEllipse(int(cx - r), int(cy - r), 2 * r, 2 * r)

    def _paint_waveform(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        bar_w, gap = 4, 3
        total = _BAR_COUNT * (bar_w + gap) - gap
        x0 = (w - total) // 2 - 14
        cy = h // 2
        p.setBrush(_ACCENT)
        for i, level in enumerate(self._levels):
            bar_h = max(2, int(level * (h - 10)))
            p.drawRoundedRect(x0 + i * (bar_w + gap), cy - bar_h // 2, bar_w, bar_h, 2, 2)

        p.setPen(_TEXT_DIM)
        p.setFont(QFont("Segoe UI", 8))
        elapsed = int(time.monotonic() - self._record_started)
        suffix = " 🔒" if self._state == "recording-locked" else ""
        p.drawText(
            self.rect().adjusted(0, 0, -10, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{elapsed // 60}:{elapsed % 60:02d}{suffix}",
        )

        # cleanup-mode dot on the left
        if self._cleanup_enabled():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_ACCENT)
            p.drawEllipse(10, cy - 3, 6, 6)

    def _paint_processing(self, p: QPainter) -> None:
        cy = self.height() // 2
        p.setBrush(_PROCESSING)
        for i in range(3):
            phase = (self._pulse + i / 3.0) % 1.0
            r = 3 + 2 * abs(math.sin(phase * math.pi))
            p.drawEllipse(
                int(self.width() / 2 - 24 + i * 20 - r), int(cy - r), int(2 * r), int(2 * r)
            )

    # ── Interaction ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_click:
            self._on_click()
