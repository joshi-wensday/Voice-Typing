"""Locate the text caret on screen (Win32), falling back to the mouse position.

GetGUIThreadInfo reports the caret for classic Win32 edit controls. Many modern
apps (Electron, browsers) draw their own caret, in which case the mouse position
is a good proxy — you usually just clicked where you're about to dictate.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def caret_screen_point() -> tuple[int, int] | None:
    """Screen coordinates just below the text caret, or None if unavailable."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        info = _GUITHREADINFO(cbSize=ctypes.sizeof(_GUITHREADINFO))
        if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
            return None
        if not info.hwndCaret:
            return None
        rect = info.rcCaret
        if rect.right - rect.left <= 0 and rect.bottom - rect.top <= 0:
            return None
        point = wintypes.POINT(rect.left, rect.bottom)
        user32.ClientToScreen(info.hwndCaret, ctypes.byref(point))
        return point.x, point.y
    except Exception:
        return None


def mouse_screen_point() -> tuple[int, int] | None:
    try:
        point = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y
    except Exception:
        return None


def preview_anchor_point() -> tuple[int, int] | None:
    """Best guess for where dictated text will land: caret, else mouse."""
    return caret_screen_point() or mouse_screen_point()
