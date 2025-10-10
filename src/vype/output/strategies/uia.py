"""UIA strategy using pywinauto for robust text injection in modern apps.

Note: This is a simplified approach. Real implementations target the focused control.
"""

from __future__ import annotations

try:
    from pywinauto import Application  # type: ignore
    from pywinauto.keyboard import send_keys  # type: ignore
except Exception:  # pragma: no cover - pywinauto not present in all envs
    Application = None  # type: ignore
    send_keys = None  # type: ignore


class UIAStrategy:
    def is_available(self) -> bool:
        return Application is not None and send_keys is not None

    def inject_text(self, text: str) -> bool:
        if not self.is_available():
            return False
        # As a generic approach, use send_keys which integrates with UIA in many apps.
        try:
            send_keys(text, with_spaces=True)
            return True
        except Exception:
            return False

    def press_key(self, key: str) -> bool:
        if send_keys is None:
            return False
        try:
            # pywinauto uses braces for special keys
            special = {
                "enter": "{ENTER}",
                "tab": "{TAB}",
                "backspace": "{BACKSPACE}",
            }.get(key.lower(), key)
            send_keys(special)
            return True
        except Exception:
            return False
