import json
from urllib.parse import parse_qs, urlsplit

import requests
from google_auth_oauthlib.flow import InstalledAppFlow


def test_google_oauth_flow_preserves_pkce_and_token_exchange(monkeypatch):
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": "example.invalid",
                "client_secret": "not-a-secret",
                "auth_uri": "https://example.invalid/authorize",
                "token_uri": "https://example.invalid/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=["openid"],
        autogenerate_code_verifier=True,
    )
    flow.redirect_uri = "http://localhost"
    authorization_url, state = flow.authorization_url()
    query = parse_qs(urlsplit(authorization_url).query)
    assert query["state"] == [state]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"]

    observed = {}

    def token_response(self, method, url, **kwargs):
        observed.update(method=method, url=url, data=kwargs["data"])
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.request = requests.Request(method, url, data=kwargs["data"]).prepare()
        response._content = json.dumps(
            {"access_token": "test-token", "token_type": "Bearer", "expires_in": 3600}
        ).encode()
        return response

    monkeypatch.setattr(requests.sessions.Session, "request", token_response)
    token = flow.fetch_token(code="test-code")
    assert token["access_token"] == "test-token"
    assert observed["method"] == "POST"
    assert observed["url"] == "https://example.invalid/token"
    assert observed["data"]["code_verifier"] == flow.code_verifier
    assert observed["data"]["code"] == "test-code"
