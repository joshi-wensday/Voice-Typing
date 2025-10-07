from __future__ import annotations

from unittest.mock import MagicMock, patch

from voice_typing.ui.hotkey import HotkeyManager


def test_hotkey_registers_with_keyboard() -> None:
    with patch("voice_typing.ui.hotkey.keyboard") as kb:
        kb.add_hotkey = MagicMock()
        hk = HotkeyManager("ctrl+alt+space", lambda: None)
        assert hk.register() is True
        kb.add_hotkey.assert_called()
