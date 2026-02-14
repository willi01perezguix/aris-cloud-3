from aris_control_2.app.admin_console import AdminConsole
from aris_control_2.app.state import SessionState


class StubTenantsClient:
    pass


class StubStoresClient:
    def __init__(self, stores):
        self._stores = stores
        self.create_called = False

    def list_stores(self, access_token: str, tenant_id: str, **kwargs):
        return {"rows": self._stores, "page": 1, "page_size": len(self._stores) or 1, "total": len(self._stores)}


class StubUsersClient:
    def __init__(self) -> None:
        self.create_calls = 0

    def create_user(self, access_token: str, user_payload: dict, idempotency_key: str):
        self.create_calls += 1
        return {"ok": True}


def test_create_user_blocks_store_tenant_mismatch(monkeypatch, capsys) -> None:
    console = AdminConsole(
        tenants=StubTenantsClient(),
        stores=StubStoresClient(stores=[{"id": "store-1", "tenant_id": "tenant-other"}]),
        users=StubUsersClient(),
    )
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-effective", selected_tenant_id="tenant-1")

    answers = iter(["john", "john@example.com", "ADMIN", "Secret123", "store-1"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    console._create_user(session)

    output = capsys.readouterr().out
    assert "mismatch tenant/store" in output
    assert console.users.create_calls == 0
