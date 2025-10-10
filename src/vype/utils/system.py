from __future__ import annotations

import ctypes
import os


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0  # type: ignore[attr-defined]
    except Exception:
        return False


class SingleInstance:
    """Windows single-instance guard using a named mutex."""

    def __init__(self, name: str = "VoiceTypingSingletonMutex") -> None:
        self._name = name
        self._handle = None

    def acquire(self) -> bool:
        try:
            CreateMutex = ctypes.windll.kernel32.CreateMutexW  # type: ignore[attr-defined]
            GetLastError = ctypes.windll.kernel32.GetLastError  # type: ignore[attr-defined]
            self._handle = CreateMutex(None, ctypes.c_bool(False), self._name)
            # ERROR_ALREADY_EXISTS = 183
            return GetLastError() != 183
        except Exception:
            return True  # best-effort: allow run

    def release(self) -> None:
        try:
            if self._handle:
                ctypes.windll.kernel32.CloseHandle(self._handle)  # type: ignore[attr-defined]
        except Exception:
            pass
