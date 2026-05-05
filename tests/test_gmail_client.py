import base64

from gmailstream.gmail_client import fetch_attachments, search_messages


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

    def get(self, userId, id):
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
