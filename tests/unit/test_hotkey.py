from __future__ import annotations

from unittest.mock import MagicMock, patch

from vype.ui.hotkey import HotkeyManager


def test_hotkey_registers_with_keyboard() -> None:
    with patch("vype.ui.hotkey.keyboard") as kb:
        kb.add_hotkey = MagicMock()
        hk = HotkeyManager("ctrl+alt+space", lambda: None)
        assert hk.register() is True
        kb.add_hotkey.assert_called()
