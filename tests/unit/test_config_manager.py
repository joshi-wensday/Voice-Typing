import os
from pathlib import Path

from voice_typing.config.manager import ConfigManager


def test_load_creates_default_tmp(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    assert cfg_path.exists()
    assert mgr.config.stt.model in {"tiny", "base", "small", "medium", "large-v2"}


def test_update_nested_values(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.update(stt__model="small", ui__hotkey="ctrl+alt+space")
    assert mgr.config.stt.model == "small"
    assert mgr.config.ui.hotkey == "ctrl+alt+space"


def test_custom_command_add(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.add_custom_command("email", r"\\b(insert email)\\b", "you@example.com")
    assert "email" in mgr.config.commands.custom_commands
    assert mgr.config.commands.custom_commands["email"].action == "you@example.com"
