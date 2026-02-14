from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient
from aris_control_2.clients.aris3_client_sdk.modules.auth_client import AuthClient
from aris_control_2.clients.aris3_client_sdk.modules.me_client import MeClient


class AuthAdapter:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.auth_store = auth_store
        self.auth_client = AuthClient(http=http, auth_store=auth_store)
        self.me_client = MeClient(http=http, auth_store=auth_store)

    def login(self, username_or_email: str, password: str) -> dict:
        return self.auth_client.login(username_or_email=username_or_email, password=password)

    def me(self) -> dict:
        return self.me_client.get_me()
