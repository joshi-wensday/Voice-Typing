"""Windows-native global hotkey using RegisterHotKey (user32).

Registers and processes WM_HOTKEY on the SAME thread.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import ctypes
from ctypes import wintypes


user32 = ctypes.windll.user32  # type: ignore[attr-defined]

# Modifiers
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

WM_HOTKEY = 0x0312


@dataclass
class ParsedHotkey:
    mods: int
    vk: int


VK_MAP = {
    "space": 0x20,
    "z": 0x5A,
    # Add more as needed
}


def parse_hotkey_string(spec: str) -> ParsedHotkey:
    """Parse strings like 'ctrl+shift+space' into modifiers and VK code."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    mods = 0
    vk = 0
    for p in parts:
        if p in ("ctrl", "control"): mods |= MOD_CONTROL
        elif p == "alt": mods |= MOD_ALT
        elif p == "shift": mods |= MOD_SHIFT
        elif p in ("win", "meta"): mods |= MOD_WIN
        else:
            vk = VK_MAP.get(p, 0)
    if vk == 0:
        raise ValueError(f"Unknown key in hotkey spec: {spec}")
    return ParsedHotkey(mods=mods, vk=vk)


class Win32Hotkey:
    def __init__(self, hotkey: str, on_toggle: Callable[[], None]) -> None:
        self.hotkey = hotkey
        self.on_toggle = on_toggle
        self._registered = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._success = False
        self._id = 1  # arbitrary id
        self.active_spec: Optional[str] = None

    def is_available(self) -> bool:
        try:
            _ = user32.RegisterHotKey
            return True
        except Exception:
            return False

    def register(self) -> bool:
        return self.register_from_candidates([self.hotkey])

    def register_from_candidates(self, specs: Iterable[str]) -> bool:
        if not self.is_available():
            return False
        if self._registered:
            return True
        # Start background thread; it will REGISTER and PUMP messages
        self._thread = threading.Thread(target=self._thread_main, args=(list(specs),), daemon=True)
        self._thread.start()
        # Wait for registration outcome
        self._ready.wait(timeout=2.0)
        return self._success

    def _thread_main(self, specs: list[str]) -> None:
        msg = wintypes.MSG()
        # Try candidates until one registers
        for spec in specs:
            try:
                parsed = parse_hotkey_string(spec)
                if user32.RegisterHotKey(None, self._id, parsed.mods, parsed.vk):
                    self._registered = True
                    self._success = True
                    self.active_spec = spec
                    print(f"[Win32Hotkey] Registered: {spec} (mods={parsed.mods:#x}, vk={parsed.vk:#x})")
                    break
            except Exception as e:
                continue
        # Signal readiness
        self._ready.set()
        if not self._registered:
            return
        # Message loop; GetMessage blocks and delivers WM_HOTKEY to THIS thread
        try:
            while not self._stop.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self._id:
                    print("[Win32Hotkey] HOTKEY fired")
                    try:
                        self.on_toggle()
                    except Exception:
                        pass
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            try:
                user32.UnregisterHotKey(None, self._id)
            except Exception:
                pass
            self._registered = False

    def unregister(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            # Post a WM_QUIT by posting 0 to GetMessage via PostThreadMessageW is more complex; rely on _stop and close
            pass
