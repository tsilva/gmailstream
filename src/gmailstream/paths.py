from pathlib import Path

DEFAULT_BASE_DIR = Path.home() / ".config" / "gmailstream"
DEFAULT_ENV_FILE = DEFAULT_BASE_DIR / ".env"
DEFAULT_PROFILES_DIR = DEFAULT_BASE_DIR / "profiles"


def get_profiles_dir(override: str | None = None) -> Path:
    """Return the active profiles directory.

    Priority:
    1. Explicit override (--profile-dir flag or GMAIL_STREAMER_PROFILE_DIR env var)
    2. ~/.config/gmailstream/profiles/ (default)
    """
    if override:
        return Path(override).resolve()
    return DEFAULT_PROFILES_DIR


def resolve_profile(name: str, profiles_dir: Path) -> Path:
    """Resolve a profile name or path to a directory.

    If `name` is an existing directory, use it directly (backward compat).
    Otherwise only simple profile names are looked up as {profiles_dir}/{name}/.
    """
    candidate = Path(name).expanduser()
    if candidate.is_dir():
        return candidate.resolve()
    if candidate.is_absolute() or "/" in name or "\\" in name:
        return candidate.resolve()
    return profiles_dir / name


def list_profiles(profiles_dir: Path) -> list[str]:
    """Return profile names (subdirectories containing config.yaml)."""
    if not profiles_dir.is_dir():
        return []
    return sorted(
        d.name for d in profiles_dir.iterdir()
        if d.is_dir() and (d / "config.yaml").exists()
    )
