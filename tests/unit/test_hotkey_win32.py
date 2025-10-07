from __future__ import annotations

from voice_typing.ui.hotkey_win32 import parse_hotkey_string, MOD_CONTROL, MOD_SHIFT, VK_MAP


def test_parse_ctrl_shift_space() -> None:
    parsed = parse_hotkey_string("ctrl+shift+space")
    assert parsed.mods & MOD_CONTROL
    assert parsed.mods & MOD_SHIFT
    assert parsed.vk == VK_MAP["space"]
