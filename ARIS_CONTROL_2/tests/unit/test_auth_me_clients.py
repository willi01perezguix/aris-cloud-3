from clients.aris3_client_sdk.auth_client import AuthClient
from clients.aris3_client_sdk.http_client import HttpClient
from clients.aris3_client_sdk.me_client import MeClient


class DummyHttpClient(HttpClient):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def request(self, method, path, token=None, json_body=None, headers=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "token": token,
                "json_body": json_body,
                "headers": headers,
            }
        )
        return {"access_token": "at", "must_change_password": False, "id": "user-1"}


def test_login_uses_username_or_email() -> None:
    http = DummyHttpClient()
    client = AuthClient(http)

    client.login("admin@aris.local", "secret")

    assert http.calls[0]["method"] == "POST"
    assert http.calls[0]["path"] == "/aris3/auth/login"
    assert http.calls[0]["json_body"] == {"username_or_email": "admin@aris.local", "password": "secret"}


def test_me_uses_bearer_token() -> None:
    http = DummyHttpClient()
    client = MeClient(http)

    client.get_me("token-123")

    assert http.calls[0]["method"] == "GET"
    assert http.calls[0]["path"] == "/aris3/me"
    assert http.calls[0]["token"] == "token-123"
