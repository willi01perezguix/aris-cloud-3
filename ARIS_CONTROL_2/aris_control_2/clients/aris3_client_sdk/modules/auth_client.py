from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


class AuthClient:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.http = http
        self.auth_store = auth_store

    def login(self, username_or_email: str, password: str) -> dict:
        payload = {"username_or_email": username_or_email, "password": password}
        result = self.http.request("POST", "/auth/login", json=payload)
        token = result.get("access_token")
        if token:
            self.auth_store.set_token(token)
        return result
