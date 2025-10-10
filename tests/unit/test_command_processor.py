from __future__ import annotations

from vype.commands.processor import CommandProcessor
from vype.commands.definitions import NewLineCommand, PunctuationCommand, InsertTextCommand, StopDictationCommand
from vype.config.schema import AppConfig, PunctuationMode, CommandConfig


def make_cfg() -> AppConfig:
    return AppConfig()


def test_new_line_extraction() -> None:
    cfg = make_cfg()
    proc = CommandProcessor(cfg)
    text, cmds = proc.process("Hello new line world")
    assert text == "Hello world"
    assert any(isinstance(c, NewLineCommand) for c in cmds)


def test_manual_punctuation_in_manual_mode() -> None:
    cfg = make_cfg()
    cfg.punctuation.mode = PunctuationMode.MANUAL
    proc = CommandProcessor(cfg)
    text, cmds = proc.process("Hello comma world period")
    assert text == "Hello world"
    symbols = [c.symbol for c in cmds if isinstance(c, PunctuationCommand)]
    assert symbols == [",", "."]


def test_hybrid_skips_duplicate_trailing_punctuation() -> None:
    cfg = make_cfg()
    cfg.punctuation.mode = PunctuationMode.HYBRID
    proc = CommandProcessor(cfg)
    # Whisper already added period at end
    text, cmds = proc.process("Hello world period.")
    # After removing the token "period", we expect a space before '.' which is acceptable to normalize later
    assert text in ("Hello world .", "Hello world.")
    # Ensure punctuation command is skipped because of trailing '.'
    assert not any(isinstance(c, PunctuationCommand) and c.symbol == "." for c in cmds)


def test_custom_command_inserts_text() -> None:
    cfg = make_cfg()
    cfg.commands.custom_commands["email"] = CommandConfig(
        enabled=True,
        pattern=r"\b(insert email)\b",
        action="you@example.com",
        description="Insert email address",
    )

    proc = CommandProcessor(cfg)
    text, cmds = proc.process("my address insert email thanks")
    assert text == "my address thanks"
    assert any(isinstance(c, InsertTextCommand) and c.text == "you@example.com" for c in cmds)


def test_stop_dictation_detected() -> None:
    cfg = make_cfg()
    proc = CommandProcessor(cfg)
    text, cmds = proc.process("this is a test stop dictation now")
    assert text == "this is a test now"
    assert any(isinstance(c, StopDictationCommand) for c in cmds)
