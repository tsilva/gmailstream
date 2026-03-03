import base64
import logging
import time
from datetime import datetime, timezone

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = (429, 500, 503)


def _retry_api_call(fn, max_retries=3):
    """Call fn(), retrying on transient HTTP errors with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return fn()
        except HttpError as e:
            status = e.resp.status
            if status in RETRYABLE_STATUS_CODES and attempt < max_retries - 1:
                wait = 2**attempt
                logger.debug("API returned %d, retrying in %ds (attempt %d/%d)", status, wait, attempt + 1, max_retries)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"API call failed after {max_retries} retries")


def search_messages(
    service, query: str, after_date: str | None = None, before_date: str | None = None
) -> list[str]:
    """Return all message IDs matching the query.

    If after_date/before_date (YYYY-MM-DD) are provided, appends Gmail date filters.
    """
    if after_date:
        query = f"{query} after:{after_date}"
    if before_date:
        query = f"{query} before:{before_date}"
    logger.debug("Searching: %s", query)
    ids = []
    request = service.users().messages().list(userId="me", q=query)
    while request:
        response = _retry_api_call(lambda: request.execute())
        for msg in response.get("messages", []):
            ids.append(msg["id"])
        request = service.users().messages().list_next(request, response)
    return ids


def fetch_raw_message(service, msg_id: str) -> bytes:
    """Fetch the full RFC 2822 message as bytes."""
    logger.debug("Fetching raw message %s", msg_id)
    msg = _retry_api_call(
        lambda: service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
    )
    try:
        return base64.urlsafe_b64decode(msg["raw"])
    except (KeyError, ValueError) as e:
        raise ValueError(f"Failed to decode raw message {msg_id}: {e}") from e


def fetch_message_metadata(service, msg_id: str) -> dict:
    """Fetch message metadata and return a dict with key fields."""
    logger.debug("Fetching metadata for %s", msg_id)
    msg = _retry_api_call(
        lambda: service.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
        ).execute()
    )

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    internal_ts = int(msg.get("internalDate", "0")) / 1000
    internal_date = datetime.fromtimestamp(internal_ts, tz=timezone.utc).strftime("%Y-%m-%d")

    return {
        "id": msg_id,
        "date": internal_date,
        "subject": headers.get("Subject", ""),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "snippet": msg.get("snippet", ""),
        "label_ids": msg.get("labelIds", []),
    }


def fetch_attachments(service, msg_id: str) -> list[dict]:
    """Return list of {filename, data} for each attachment."""
    logger.debug("Fetching attachments for %s", msg_id)
    msg = _retry_api_call(
        lambda: service.users().messages().get(userId="me", id=msg_id).execute()
    )
    attachments = []
    for part in msg.get("payload", {}).get("parts", []):
        filename = part.get("filename")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            att = _retry_api_call(
                lambda: service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=msg_id, id=attachment_id)
                .execute()
            )
            try:
                data = base64.urlsafe_b64decode(att["data"])
            except (KeyError, ValueError) as e:
                logger.warning("Failed to decode attachment '%s' for message %s: %s", filename, msg_id, e)
                continue
            attachments.append({"filename": filename, "data": data})
    return attachments
