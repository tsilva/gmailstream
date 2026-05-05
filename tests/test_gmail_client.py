import base64

from gmailstream.gmail_client import fetch_attachments, fetch_message_metadata, search_messages


class _Request:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class _AttachmentsResource:
    def __init__(self, attachment_responses):
        self.attachment_responses = attachment_responses

    def get(self, userId, messageId, id):
        return _Request(self.attachment_responses[id])


class _MessagesResource:
    def __init__(self, message_response=None, attachment_responses=None):
        self.message_response = message_response or {}
        self.attachment_responses = attachment_responses or {}
        self.list_queries = []

    def list(self, userId, q):
        self.list_queries.append(q)
        return _Request({"messages": [{"id": "msg-1"}]})

    def list_next(self, request, response):
        return None

    def get(self, userId, id, **kwargs):
        return _Request(self.message_response)

    def attachments(self):
        return _AttachmentsResource(self.attachment_responses)


class _UsersResource:
    def __init__(self, messages_resource):
        self.messages_resource = messages_resource

    def messages(self):
        return self.messages_resource


class _Service:
    def __init__(self, messages_resource):
        self.messages_resource = messages_resource

    def users(self):
        return _UsersResource(self.messages_resource)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def test_search_messages_formats_iso_dates_for_gmail_query():
    messages = _MessagesResource()
    service = _Service(messages)

    result = search_messages(
        service,
        "from:sender@example.com",
        after_date="2024-01-01",
        before_date="2024-02-01",
    )

    assert result == ["msg-1"]
    assert messages.list_queries == [
        "from:sender@example.com after:2024/01/01 before:2024/02/01"
    ]


def test_fetch_attachments_walks_nested_parts_and_direct_body_data():
    messages = _MessagesResource(
        message_response={
            "payload": {
                "parts": [
                    {
                        "mimeType": "multipart/mixed",
                        "parts": [
                            {
                                "filename": "nested.txt",
                                "body": {"attachmentId": "att-1"},
                            }
                        ],
                    },
                    {
                        "filename": "inline.txt",
                        "body": {"data": _b64(b"inline-data")},
                    },
                ]
            }
        },
        attachment_responses={"att-1": {"data": _b64(b"nested-data")}},
    )
    service = _Service(messages)

    attachments = fetch_attachments(service, "msg-1")

    assert attachments == [
        {"filename": "nested.txt", "data": b"nested-data"},
        {"filename": "inline.txt", "data": b"inline-data"},
    ]


def test_fetch_message_metadata_prefers_email_date_header_over_internal_date():
    messages = _MessagesResource(
        message_response={
            "id": "msg-1",
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "Date", "value": "Fri, 12 Jan 2024 23:30:00 -0500"},
                    {"name": "Subject", "value": "Invoice"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                ]
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2024-01-12"
    assert metadata["date_source"] == "header"
    assert metadata["internal_date"] == "2026-05-05"
    assert metadata["subject"] == "Invoice"
    assert metadata["from"] == "sender@example.com"
    assert metadata["to"] == "recipient@example.com"


def test_fetch_message_metadata_reads_headers_case_insensitively():
    messages = _MessagesResource(
        message_response={
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "date", "value": "Mon, 01 Apr 2024 08:15:00 +0100"},
                    {"name": "subject", "value": "Lowercase headers"},
                ]
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2024-04-01"
    assert metadata["subject"] == "Lowercase headers"


def test_fetch_message_metadata_falls_back_to_internal_date_when_header_is_invalid():
    messages = _MessagesResource(
        message_response={
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "Date", "value": "not a real date"},
                ]
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2026-05-05"
    assert metadata["date_source"] == "internal"
    assert metadata["internal_date"] == "2026-05-05"


def test_fetch_message_metadata_prefers_inline_forwarded_date_for_forwarded_subject():
    messages = _MessagesResource(
        message_response={
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "Date", "value": "Tue, 05 May 2026 12:00:00 +0000"},
                    {
                        "name": "Subject",
                        "value": "Fwd: Cartao Continente envio de fatura eletronica",
                    },
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": _b64(
                                b"---------- Forwarded message ---------\n"
                                b"From: Cartao Continente <noreply@example.com>\n"
                                b"Date: Fri, 12 Jan 2024 23:30:00 +0000\n"
                                b"Subject: Cartao Continente envio de fatura eletronica\n"
                            )
                        },
                    }
                ],
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2024-01-12"
    assert metadata["date_source"] == "forwarded"
    assert metadata["internal_date"] == "2026-05-05"


def test_fetch_message_metadata_reads_portuguese_forwarded_date_line():
    messages = _MessagesResource(
        message_response={
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "Date", "value": "Tue, 05 May 2026 12:00:00 +0000"},
                    {"name": "Subject", "value": "Fwd: Fatura eletronica"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": _b64(
                                b"---------- Mensagem encaminhada ---------\n"
                                b"De: Cartao Continente <noreply@example.com>\n"
                                b"Data: 03/04/2024 09:15\n"
                                b"Assunto: Fatura eletronica\n"
                            )
                        },
                    }
                ],
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2024-04-03"
    assert metadata["date_source"] == "forwarded"


def test_fetch_message_metadata_prefers_attached_forwarded_message_date():
    messages = _MessagesResource(
        message_response={
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "Date", "value": "Tue, 05 May 2026 12:00:00 +0000"},
                    {"name": "Subject", "value": "FW: Invoice"},
                ],
                "parts": [
                    {
                        "mimeType": "message/rfc822",
                        "headers": [
                            {"name": "Date", "value": "Mon, 01 Apr 2024 08:15:00 +0100"},
                            {"name": "Subject", "value": "Invoice"},
                        ],
                    }
                ],
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2024-04-01"
    assert metadata["date_source"] == "forwarded"


def test_fetch_message_metadata_uses_attachment_filename_date_for_forwarded_subject():
    messages = _MessagesResource(
        message_response={
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "Date", "value": "Tue, 05 May 2026 12:00:00 +0000"},
                    {
                        "name": "Subject",
                        "value": "Fwd: Cartao Continente envio de fatura eletronica",
                    },
                ],
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": _b64(b"Caro(a) Cliente")},
                            }
                        ],
                    },
                    {
                        "mimeType": "application/pdf",
                        "filename": "Fatura_Cartao_Continente_20260130_0954.pdf",
                    },
                ],
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2026-01-30"
    assert metadata["date_source"] == "attachment_filename"


def test_fetch_message_metadata_uses_earliest_attachment_filename_date():
    messages = _MessagesResource(
        message_response={
            "internalDate": "1777996800000",
            "payload": {
                "headers": [
                    {"name": "Date", "value": "Tue, 05 May 2026 12:00:00 +0000"},
                    {"name": "Subject", "value": "Fwd: Faturas"},
                ],
                "parts": [
                    {
                        "mimeType": "application/pdf",
                        "filename": "Fatura_Cartao_Continente_20251220_1342.pdf",
                    },
                    {
                        "mimeType": "application/pdf",
                        "filename": "Fatura_Cartao_Continente_2025-12-18.pdf",
                    },
                ],
            },
        }
    )
    service = _Service(messages)

    metadata = fetch_message_metadata(service, "msg-1")

    assert metadata["date"] == "2025-12-18"
    assert metadata["date_source"] == "attachment_filename"
