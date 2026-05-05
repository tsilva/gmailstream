import os
from pathlib import Path

from gmailstream.paths import DEFAULT_ENV_FILE


def load_app_env(env_file: Path = DEFAULT_ENV_FILE) -> None:
    """Load environment variables from the app config .env file."""
    if not env_file.is_file():
        return

    for line in env_file.read_text().splitlines():
        key_value = _parse_env_line(line)
        if key_value is None:
            continue

        key, value = key_value
        os.environ.setdefault(key, value)


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]

    return key, value
