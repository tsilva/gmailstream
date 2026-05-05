import base64
import html
import logging
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = (429, 500, 503)
FORWARDED_SUBJECT_RE = re.compile(r"^\s*(fwd?|enc|reenc|encaminhado)\s*:", re.IGNORECASE)
FORWARDED_MARKER_RE = re.compile(
    r"(forwarded message|begin forwarded message|mensagem (re)?encaminhada)",
    re.IGNORECASE,
)
FORWARDED_DATE_RE = re.compile(r"^\s*(date|sent|data|enviad[ao])\s*:\s*(.+)\s*$", re.IGNORECASE)
FILENAME_ISO_DATE_RE = re.compile(r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)")


def _retry_api_call(fn, max_retries=3):
    """Call fn(), retrying on transient HTTP errors with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return fn()
        except HttpError as e:
            status = e.resp.status
            if status in RETRYABLE_STATUS_CODES and attempt < max_retries - 1:
                wait = 2**attempt
                logger.debug(
                    "API returned %d, retrying in %ds (attempt %d/%d)",
                    status,
                    wait,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"API call failed after {max_retries} retries")


def _format_gmail_search_date(date: str) -> str:
    """Convert YYYY-MM-DD input to Gmail search date syntax."""
    return datetime.strptime(date, "%Y-%m-%d").strftime("%Y/%m/%d")


def _decode_base64url(data: str) -> bytes:
    """Decode Gmail's base64url strings, which may omit padding."""
    padded = data + ("=" * (-len(data) % 4))
    return base64.urlsafe_b64decode(padded)


def _get_header(headers: dict[str, str], name: str) -> str:
    """Return a header value using case-insensitive lookup."""
    normalized = name.lower()
    for header_name, value in headers.items():
        if header_name.lower() == normalized:
            return value
    return ""


def _date_from_email_header(value: str) -> str | None:
    """Parse an RFC email Date header into YYYY-MM-DD without timezone conversion."""
    if not value:
        return None

    normalized = re.sub(r"\s+at\s+", " ", value.strip(), flags=re.IGNORECASE)
    try:
        return parsedate_to_datetime(normalized).date().isoformat()
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def _date_from_numeric_text(value: str) -> str | None:
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", value)
    if not match:
        return None

    first = int(match.group(1))
    second = int(match.group(2))
    year = int(match.group(3))
    if year < 100:
        year += 2000

    if first > 12:
        day, month = first, second
    elif second > 12:
        month, day = first, second
    else:
        day, month = first, second

    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _date_from_filename(value: str) -> str | None:
    match = FILENAME_ISO_DATE_RE.search(value)
    if not match:
        return None

    try:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        ).date().isoformat()
    except ValueError:
        return None


def _date_from_forwarded_text(text: str) -> str | None:
    marker = FORWARDED_MARKER_RE.search(text)
    if not marker:
        return None

    lines = text[marker.start() :].splitlines()
    for line in lines[:80]:
        match = FORWARDED_DATE_RE.match(line)
        if not match:
            continue

        value = match.group(2)
        return _date_from_email_header(value) or _date_from_numeric_text(value)
    return None


def _part_text(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""

    try:
        text = _decode_base64url(data).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""

    if part.get("mimeType") == "text/html":
        text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
        text = re.sub(r"(?i)</\s*(div|p|tr|li|blockquote|h[1-6])\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
    return text


def _forwarded_date_from_payload(payload: dict) -> str | None:
    for part in payload.get("parts", []):
        headers = {h["name"]: h["value"] for h in part.get("headers", [])}
        nested_date = _date_from_email_header(_get_header(headers, "Date"))
        if nested_date and part.get("mimeType") == "message/rfc822":
            return nested_date

        text_date = _date_from_forwarded_text(_part_text(part))
        if text_date:
            return text_date

        child_date = _forwarded_date_from_payload(part)
        if child_date:
            return child_date
    return None


def _attachment_date_from_payload(payload: dict) -> str | None:
    dates = []
    for part in payload.get("parts", []):
        filename = part.get("filename") or ""
        date = _date_from_filename(filename)
        if date:
            dates.append(date)

        child_date = _attachment_date_from_payload(part)
        if child_date:
            dates.append(child_date)

    return min(dates) if dates else None


def _is_forwarded_subject(subject: str) -> bool:
    return bool(FORWARDED_SUBJECT_RE.match(subject))


def search_messages(
    service, query: str, after_date: str | None = None, before_date: str | None = None
) -> list[str]:
    """Return all message IDs matching the query.

    If after_date/before_date (YYYY-MM-DD) are provided, appends Gmail date filters.
    """
    if after_date:
        query = f"{query} after:{_format_gmail_search_date(after_date)}"
    if before_date:
        query = f"{query} before:{_format_gmail_search_date(before_date)}"
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
        return _decode_base64url(msg["raw"])
    except (KeyError, ValueError) as e:
        raise ValueError(f"Failed to decode raw message {msg_id}: {e}") from e


def fetch_message_metadata(service, msg_id: str) -> dict:
    """Fetch message metadata and return a dict with key fields."""
    logger.debug("Fetching metadata for %s", msg_id)
    msg = _retry_api_call(
        lambda: service.users()
        .messages()
        .get(
            userId="me",
            id=msg_id,
            format="full",
        )
        .execute()
    )

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    internal_ts = int(msg.get("internalDate", "0")) / 1000
    internal_date = datetime.fromtimestamp(internal_ts, tz=timezone.utc).strftime("%Y-%m-%d")
    subject = _get_header(headers, "Subject")
    header_date = _date_from_email_header(_get_header(headers, "Date"))
    forwarded_date = None
    attachment_date = None
    if _is_forwarded_subject(subject):
        forwarded_date = _forwarded_date_from_payload(msg.get("payload", {}))
        attachment_date = _attachment_date_from_payload(msg.get("payload", {}))
    message_date = forwarded_date or attachment_date or header_date or internal_date

    return {
        "id": msg_id,
        "date": message_date,
        "date_source": (
            "forwarded"
            if forwarded_date
            else "attachment_filename"
            if attachment_date
            else "header"
            if header_date
            else "internal"
        ),
        "internal_date": internal_date,
        "subject": subject,
        "from": _get_header(headers, "From"),
        "to": _get_header(headers, "To"),
        "snippet": msg.get("snippet", ""),
        "label_ids": msg.get("labelIds", []),
    }


def _walk_parts(part: dict):
    yield part
    for child in part.get("parts", []):
        yield from _walk_parts(child)


def fetch_attachments(service, msg_id: str) -> list[dict]:
    """Return list of {filename, data} for each attachment."""
    logger.debug("Fetching attachments for %s", msg_id)
    msg = _retry_api_call(
        lambda: service.users().messages().get(userId="me", id=msg_id).execute()
    )
    attachments = []
    for part in _walk_parts(msg.get("payload", {})):
        filename = part.get("filename")
        body = part.get("body", {})
        if not filename:
            continue

        try:
            attachment_id = body.get("attachmentId")
            if attachment_id:
                att = _retry_api_call(
                    lambda: service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_id, id=attachment_id)
                    .execute()
                )
                data = _decode_base64url(att["data"])
            elif "data" in body:
                data = _decode_base64url(body["data"])
            else:
                continue
        except (KeyError, ValueError) as e:
            logger.warning(
                "Failed to decode attachment '%s' for message %s: %s",
                filename,
                msg_id,
                e,
            )
            continue

        attachments.append({"filename": filename, "data": data})
    return attachments
