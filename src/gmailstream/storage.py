import json
import logging
import os
import re
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath

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


def ensure_private_export_dir(path: Path) -> None:
    """Create an export directory readable only by the current user."""
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)


def _private_message_dir(target_dir: Path, msg_id: str, date: str, subject: str) -> Path:
    ensure_private_export_dir(target_dir)
    ensure_private_export_dir(_month_dir(target_dir, date))
    dest = _message_dir(target_dir, msg_id, date, subject)
    ensure_private_export_dir(dest)
    return dest


def _write_private_bytes(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if os.name != "nt":
            os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
        if os.name != "nt":
            path.chmod(0o600)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _write_private_text(path: Path, text: str) -> None:
    _write_private_bytes(path, text.encode())


def _write_new_private_bytes(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if os.name != "nt":
            path.chmod(0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _unique_path(dest: Path, filename: str) -> Path:
    """Return a unique file path, appending (1), (2), etc. if needed."""
    path = dest / filename
    if not path.exists() and not path.is_symlink():
        return path
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = dest / f"{stem} ({counter}){suffix}"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        counter += 1


def _safe_attachment_filename(filename: str) -> str:
    """Return a local attachment filename, rejecting path-like input."""
    raw = str(filename).strip()
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)

    if (
        not raw
        or Path(raw).is_absolute()
        or PureWindowsPath(raw).is_absolute()
        or normalized != path.name
        or path.name in {".", ".."}
    ):
        raise ValueError(f"Unsafe attachment filename: {filename!r}")

    return path.name


def save_eml(target_dir: Path, msg_id: str, date: str, subject: str, raw: bytes):
    """Save message.eml inside a per-message directory."""
    dest = _message_dir(target_dir, msg_id, date, subject)
    try:
        dest = _private_message_dir(target_dir, msg_id, date, subject)
        logger.debug("Saving message.eml to %s", dest)
        _write_private_bytes(dest / "message.eml", raw)
    except OSError as e:
        raise OSError(f"Failed to save .eml for message {msg_id} to {dest}: {e}") from e


def save_metadata(target_dir: Path, msg_id: str, date: str, subject: str, metadata: dict):
    """Save metadata.json inside a per-message directory."""
    dest = _message_dir(target_dir, msg_id, date, subject)
    try:
        dest = _private_message_dir(target_dir, msg_id, date, subject)
        logger.debug("Saving metadata.json to %s", dest)
        _write_private_text(
            dest / "metadata.json",
            json.dumps(metadata, indent=2, ensure_ascii=False),
        )
    except OSError as e:
        raise OSError(f"Failed to save metadata for message {msg_id} to {dest}: {e}") from e


def save_attachments(
    target_dir: Path, msg_id: str, date: str, subject: str, attachments: list[dict]
):
    """Save attachments inside a per-message directory."""
    try:
        dest = _private_message_dir(target_dir, msg_id, date, subject)
    except OSError as e:
        raise OSError(f"Failed to create directory for attachments of message {msg_id}: {e}") from e
    for att in attachments:
        filename = _safe_attachment_filename(att["filename"])
        while True:
            filepath = _unique_path(dest, filename)
            try:
                logger.debug("Saving attachment %s", filepath)
                _write_new_private_bytes(filepath, att["data"])
                break
            except FileExistsError:
                continue
            except OSError as e:
                raise OSError(
                    f"Failed to save attachment '{filename}' for message {msg_id}: {e}"
                ) from e


def _scan_legacy_json_files(
    glob_iter, downloaded_ids: set[str], most_recent_date: str | None
) -> str | None:
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


def _read_completed_message_metadata(meta_path: Path) -> dict | None:
    try:
        meta = json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(meta, dict) or not meta.get("id"):
        return None
    return meta


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
    most_recent_date = _scan_legacy_json_files(
        target_dir.glob("* - *.json"), downloaded_ids, most_recent_date
    )

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
        most_recent_date = _scan_legacy_json_files(
            month_dir.glob("* - *.json"), downloaded_ids, most_recent_date
        )

        # Scan per-message directories (new layout)
        for msg_dir in month_dir.iterdir():
            if not msg_dir.is_dir():
                continue
            # Extract short ID from last segment: "YYYY-MM-DD - slug - {short_id}"
            parts = msg_dir.name.rsplit(" - ", 1)
            if len(parts) != 2:
                continue
            meta = _read_completed_message_metadata(msg_dir / "metadata.json")
            if meta is None:
                continue
            date = meta.get("date") or msg_dir.name[:10]
            downloaded_ids.add(_short_id(meta["id"]))
            if date and (most_recent_date is None or date > most_recent_date):
                most_recent_date = date

    return downloaded_ids, most_recent_date
