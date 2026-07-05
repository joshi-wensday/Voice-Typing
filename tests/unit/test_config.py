"""Config: defaults, YAML roundtrip, directory override via env var."""

from pathlib import Path

from vype.config import Config, config_dir, load_config, save_config


def test_defaults():
    cfg = Config()
    assert cfg.hotkey.key == "right ctrl"
    assert cfg.hotkey.tap_threshold_ms == 300
    assert cfg.stt.backend == "parakeet"
    assert cfg.stt.device == "cuda"
    assert cfg.cleanup.enabled is False
    assert cfg.audio.sample_rate == 16000
    assert cfg.ui.live_preview is True
    assert cfg.ui.preview_at_caret is True
    assert cfg.min_utterance_s == 0.3
    assert cfg.append_space is True


def test_config_dir_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("VYPE_CONFIG_DIR", str(tmp_path))
    assert config_dir() == tmp_path


def test_config_dir_default_is_home_dot_vype(monkeypatch):
    monkeypatch.delenv("VYPE_CONFIG_DIR", raising=False)
    assert config_dir() == Path.home() / ".vype"


def test_load_missing_file_creates_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("VYPE_CONFIG_DIR", str(tmp_path))
    cfg = load_config()
    assert cfg == Config()
    assert (tmp_path / "config.yaml").exists()


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("VYPE_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.hotkey.key = "f8"
    cfg.stt.backend = "whisper"
    cfg.cleanup.enabled = True
    cfg.cleanup.api_key = "sk-test"
    save_config(cfg)
    loaded = load_config()
    assert loaded == cfg


def test_load_ignores_unknown_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("VYPE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "hotkey:\n  key: f9\n  some_removed_field: true\nfuture_section:\n  x: 1\n",
        encoding="utf-8",
    )
    cfg = load_config()
    assert cfg.hotkey.key == "f9"


def test_load_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("VYPE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.yaml").write_text(":: not yaml ::[", encoding="utf-8")
    cfg = load_config()
    assert cfg == Config()
