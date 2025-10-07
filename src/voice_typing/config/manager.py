"""Configuration management with file I/O."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import AppConfig, CommandConfig


class ConfigManager:
    """Manages loading, saving, and updating configuration."""

    DEFAULT_CONFIG_PATH = Path.home() / ".voice-typing" / "config.yaml"

    def __init__(self, config_path: Path | None = None):
        """Initialize config manager.

        Args:
            config_path: Path to config file (default: ~/.voice-typing/config.yaml)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        self.config = self.load()

    def load(self) -> AppConfig:
        """Load configuration from file or create default."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return AppConfig(**data)
        # Create default config
        config = AppConfig()
        self.save(config)
        return config

    def save(self, config: AppConfig | None = None) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save (default: current config)
        """
        if config is None:
            config = self.config

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def update(self, **kwargs: Any) -> None:
        """Update specific configuration values using double-underscore nesting.

        Example:
            config.update(stt__model="small", ui__hotkey="ctrl+alt+space")
        """
        data = self.config.model_dump()

        for key, value in kwargs.items():
            keys = key.split("__")
            d: Any = data
            for k in keys[:-1]:
                d = d[k]
            d[keys[-1]] = value

        self.config = AppConfig(**data)
        self.save()

    def add_custom_command(self, name: str, pattern: str, action: str, description: str = "") -> None:
        """Add a custom voice command.

        Args:
            name: Command identifier
            pattern: Regex pattern to match in transcription
            action: Text to insert or action to perform
            description: Human-readable description
        """
        self.config.commands.custom_commands[name] = CommandConfig(
            enabled=True,
            pattern=pattern,
            action=action,
            description=description,
        )
        self.save()

    def toggle_command(self, command_path: str, enabled: bool) -> None:
        """Enable/disable a specific command.

        Args:
            command_path: Dot-separated path (e.g., "punctuation.period", "commands.new_line")
            enabled: Whether to enable the command
        """
        parts = command_path.split(".")
        obj: Any = self.config

        for part in parts[:-1]:
            obj = getattr(obj, part)

        command = getattr(obj, parts[-1])
        command.enabled = enabled
        self.save()

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = AppConfig()
        self.save()
