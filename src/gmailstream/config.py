import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ProfileConfig:
    filter: str
    target_directory: str
    mode: str = "full"  # "full" or "attachments_only"

    def __post_init__(self):
        if self.mode not in ("full", "attachments_only"):
            raise ValueError(f"Invalid mode: {self.mode!r}. Must be 'full' or 'attachments_only'.")


def load_config(profile_dir: Path) -> ProfileConfig:
    config_path = profile_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path) as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {config_path}, got {type(data).__name__}")

    if not data.get("filter"):
        raise ValueError(f"Missing or empty 'filter' key in {config_path}")

    logger.debug("Loaded config from %s: filter=%r, mode=%s", config_path, data.get("filter"), data.get("mode", "full"))

    try:
        config = ProfileConfig(**data)
    except TypeError as e:
        raise ValueError(f"Invalid config keys in {config_path}: {e}") from e

    target = Path(config.target_directory)
    if not target.is_absolute():
        config.target_directory = str((profile_dir / target).resolve())
    return config
