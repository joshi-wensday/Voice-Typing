from __future__ import annotations

from unittest.mock import MagicMock, patch

from vype.config.schema import AppConfig
from vype.output.handler import OutputHandler


def test_inject_text_uses_first_available_strategy() -> None:
    cfg = AppConfig()
    cfg.output.primary_method = "keyboard"
    cfg.output.fallback_methods = ["clipboard"]

    handler = OutputHandler(cfg)

    with patch("vype.output.strategies.keyboard.keyboard") as kb:
        kb.write = MagicMock()
        kb.send = MagicMock()
        # Available and success
        assert handler.inject_text("hello") is True
        kb.write.assert_called_once()


def test_fallback_to_clipboard_when_keyboard_fails() -> None:
    cfg = AppConfig()
    cfg.output.primary_method = "keyboard"
    cfg.output.fallback_methods = ["clipboard"]

    handler = OutputHandler(cfg)

    with patch("vype.output.strategies.keyboard.keyboard") as kb, \
         patch("vype.output.strategies.clipboard.pyperclip") as pc, \
         patch("vype.output.strategies.clipboard.keyboard") as clip_kb:
        # Keyboard available but write raises
        kb.write = MagicMock(side_effect=RuntimeError("fail"))
        kb.send = MagicMock()
        # Clipboard available and succeeds
        pc.copy = MagicMock()
        clip_kb.send = MagicMock()

        assert handler.inject_text("hello") is True
        pc.copy.assert_called_once()
