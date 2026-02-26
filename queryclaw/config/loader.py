"""Configuration loading utilities."""

import json
from pathlib import Path

from queryclaw.config.schema import Config


def get_config_dir() -> Path:
    """Get the QueryClaw configuration directory."""
    return Path.home() / ".queryclaw"


def get_config_path() -> Path:
    """Get the default configuration file path."""
    return get_config_dir() / "config.json"


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file or create default.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        Loaded configuration object.
    """
    path = config_path or get_config_path()

    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return Config.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")

    return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save configuration to file.

    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
