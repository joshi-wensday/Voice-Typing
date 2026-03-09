"""Unit tests for ConfigManager."""

from pathlib import Path

from vype.config.manager import ConfigManager


def test_load_creates_default(tmp_path: Path) -> None:
    """Loading from a non-existent path should create a valid default config."""
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    assert cfg_path.exists()
    # Default model is the Canary model
    assert mgr.config.stt.model == "nvidia/canary-qwen-2.5b"
    assert mgr.config.stt.device == "cuda"
    assert mgr.config.stt.enable_pnc is True


def test_update_nested_values(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.update(stt__model="nvidia/canary-1b", ui__hotkey="ctrl+alt+space")
    assert mgr.config.stt.model == "nvidia/canary-1b"
    assert mgr.config.ui.hotkey == "ctrl+alt+space"


def test_update_stt_pnc(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.update(stt__enable_pnc=False)
    assert mgr.config.stt.enable_pnc is False


def test_update_stt_context_tail(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.update(stt__context_tail_chars=200)
    assert mgr.config.stt.context_tail_chars == 200


def test_reset_to_defaults(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.update(stt__model="nvidia/canary-1b", stt__enable_pnc=False)
    mgr.reset_to_defaults()
    assert mgr.config.stt.model == "nvidia/canary-qwen-2.5b"
    assert mgr.config.stt.enable_pnc is True


def test_config_persists_across_reload(tmp_path: Path) -> None:
    """Changes written to disk should survive a reload."""
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.update(stt__max_new_tokens=128, ui__hotkey="ctrl+shift+v")

    mgr2 = ConfigManager(config_path=cfg_path)
    assert mgr2.config.stt.max_new_tokens == 128
    assert mgr2.config.ui.hotkey == "ctrl+shift+v"
