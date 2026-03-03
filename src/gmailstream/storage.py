import json
import logging
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)


def _short_id(msg_id: str) -> str:
    return msg_id[:8]


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if not text:
        return "no-subject"
    if len(text) > 60:
        truncated = text[:60].rsplit("-", 1)[0]
        text = truncated if truncated else text[:60]
    return text


def _month_dir(target_dir: Path, date: str) -> Path:
    """Return target_dir/YYYY-MM for a YYYY-MM-DD date string."""
    return target_dir / date[:7]


def _message_dir(target_dir: Path, msg_id: str, date: str, subject: str) -> Path:
    """Return per-message directory: target_dir/YYYY-MM/YYYY-MM-DD - slug - short_id."""
    return _month_dir(target_dir, date) / f"{date} - {_slugify(subject)} - {_short_id(msg_id)}"


def _unique_path(dest: Path, filename: str) -> Path:
    """Return a unique file path, appending (1), (2), etc. if needed."""
    path = dest / filename
    if not path.exists():
        return path
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = dest / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def save_eml(target_dir: Path, msg_id: str, date: str, subject: str, raw: bytes):
    """Save message.eml inside a per-message directory."""
    dest = _message_dir(target_dir, msg_id, date, subject)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        logger.debug("Saving message.eml to %s", dest)
        (dest / "message.eml").write_bytes(raw)
    except OSError as e:
        raise OSError(f"Failed to save .eml for message {msg_id} to {dest}: {e}") from e


def save_metadata(target_dir: Path, msg_id: str, date: str, subject: str, metadata: dict):
    """Save metadata.json inside a per-message directory."""
    dest = _message_dir(target_dir, msg_id, date, subject)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        logger.debug("Saving metadata.json to %s", dest)
        (dest / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    except OSError as e:
        raise OSError(f"Failed to save metadata for message {msg_id} to {dest}: {e}") from e


def save_attachments(target_dir: Path, msg_id: str, date: str, subject: str, attachments: list[dict]):
    """Save attachments inside a per-message directory."""
    dest = _message_dir(target_dir, msg_id, date, subject)
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(f"Failed to create directory for attachments of message {msg_id}: {e}") from e
    for att in attachments:
        filepath = _unique_path(dest, att["filename"])
        try:
            logger.debug("Saving attachment %s", filepath)
            filepath.write_bytes(att["data"])
        except OSError as e:
            raise OSError(f"Failed to save attachment '{att['filename']}' for message {msg_id}: {e}") from e


def _scan_legacy_json_files(glob_iter, downloaded_ids: set[str], most_recent_date: str | None) -> str | None:
    """Parse old flat metadata JSON files for backward compat. Extracts short IDs."""
    for meta_path in glob_iter:
        try:
            meta = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        msg_id = meta.get("id")
        date = meta.get("date")
        if msg_id:
            downloaded_ids.add(_short_id(msg_id))
        if date and (most_recent_date is None or date > most_recent_date):
            most_recent_date = date
    return most_recent_date


def scan_downloaded_metadata(
    target_dir: Path, from_date: str | None = None, to_date: str | None = None
) -> tuple[set[str], str | None]:
    """Scan for downloaded messages by directory names and legacy JSON files.

    Returns (set of short IDs, most_recent_date_or_none).
    """
    downloaded_ids: set[str] = set()
    most_recent_date: str | None = None

    if not target_dir.is_dir():
        return downloaded_ids, most_recent_date

    # Scan flat legacy JSON files in root (backward compat with pre-YYYY-MM layout)
    most_recent_date = _scan_legacy_json_files(target_dir.glob("* - *.json"), downloaded_ids, most_recent_date)

    # Scan YYYY-MM subdirectories
    for month_dir in sorted(target_dir.iterdir()):
        if not month_dir.is_dir() or len(month_dir.name) != 7:
            continue
        folder_month = month_dir.name
        if from_date and folder_month < from_date[:7]:
            continue
        if to_date and folder_month > to_date[:7]:
            continue

        # Scan legacy flat JSON files in month dir
        most_recent_date = _scan_legacy_json_files(month_dir.glob("* - *.json"), downloaded_ids, most_recent_date)

        # Scan per-message directories (new layout)
        for msg_dir in month_dir.iterdir():
            if not msg_dir.is_dir():
                continue
            # Extract short ID from last segment: "YYYY-MM-DD - slug - {short_id}"
            parts = msg_dir.name.rsplit(" - ", 1)
            if len(parts) != 2:
                continue
            short_id = parts[1]
            date = msg_dir.name[:10]
            downloaded_ids.add(short_id)
            if date and (most_recent_date is None or date > most_recent_date):
                most_recent_date = date

    return downloaded_ids, most_recent_date
