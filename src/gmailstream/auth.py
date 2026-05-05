import logging
import os
import tempfile
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def ensure_private_dir(path: Path) -> None:
    """Create a directory for local secrets and restrict it to the current user."""
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)


def write_private_bytes(path: Path, data: bytes) -> None:
    """Atomically write bytes readable only by the current user on POSIX systems."""
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


def write_private_text(path: Path, text: str) -> None:
    write_private_bytes(path, text.encode())


def copy_private_file(src: Path, dest: Path) -> None:
    write_private_bytes(dest, src.read_bytes())


def get_gmail_service(profile_dir: Path):
    ensure_private_dir(profile_dir)
    creds_path = profile_dir / "credentials.json"
    token_path = profile_dir / "token.json"

    creds = None
    if token_path.exists():
        logger.debug("Loading cached token from %s", token_path)
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except (ValueError, KeyError) as e:
            logger.debug("Cached token is corrupted (%s), will re-authenticate", e)
            token_path.unlink()
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Refreshing expired token")
            try:
                creds.refresh(Request())
            except RefreshError as e:
                logger.debug("Token refresh failed (%s), will re-authenticate", e)
                token_path.unlink(missing_ok=True)
                creds = None
        if not creds or not creds.valid:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"OAuth credentials not found: {creds_path}\n"
                    "Download from Google Cloud Console and place in profile directory."
                )
            logger.debug("Starting OAuth flow via local browser")
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except OSError as e:
                raise RuntimeError(
                    f"OAuth flow failed — could not start local server: {e}\n"
                    "Check that no other process is blocking the port and a browser is available."
                ) from e
        write_private_text(token_path, creds.to_json())
        logger.debug("Token saved to %s", token_path)

    try:
        service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        raise RuntimeError(f"Failed to build Gmail API client: {e}") from e

    logger.debug("Gmail service ready")
    return service
