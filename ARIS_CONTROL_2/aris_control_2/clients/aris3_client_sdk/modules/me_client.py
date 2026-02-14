from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


class MeClient:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.http = http
        self.auth_store = auth_store

    def get_me(self) -> dict:
        return self.http.request("GET", "/auth/me", token=self.auth_store.get_token())
