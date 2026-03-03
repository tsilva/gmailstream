import logging
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service(profile_dir: Path):
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
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        logger.debug("Token saved to %s", token_path)

    try:
        service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        raise RuntimeError(f"Failed to build Gmail API client: {e}") from e

    logger.debug("Gmail service ready")
    return service
