from pathlib import Path

from aris_control_2.app.context_store import restore_compatible_context, save_context
from aris_control_2.app.main import _restore_operator_context
from aris_control_2.app.state import SessionState
from aris_control_2.app.ui.filters import debounce_text


def test_debounce_text_waits_configured_time() -> None:
    sleeps: list[float] = []

    result = debounce_text("tenant-search", wait_ms=420, sleeper=lambda seconds: sleeps.append(seconds))

    assert result == "tenant-search"
    assert sleeps == [0.42]


def test_restore_operator_context_restores_filters_and_pagination(tmp_path: Path, monkeypatch) -> None:
    context_file = tmp_path / "operator-context.json"
    monkeypatch.setenv("ARIS3_OPERATOR_CONTEXT_PATH", str(context_file))

    save_context(
        session_fingerprint="SUPERADMIN:tenant-1",
        selected_tenant_id="tenant-1",
        filters_by_module={"users": {"q": "alice", "status": "ACTIVE"}},
        pagination_by_module={"users": {"page": 4, "page_size": 25}},
    )

    session = SessionState(role="SUPERADMIN", effective_tenant_id="tenant-1")
    _restore_operator_context(session)

    assert session.selected_tenant_id == "tenant-1"
    assert session.filters_by_module["users"]["q"] == "alice"
    assert session.pagination_by_module["users"]["page"] == 4


def test_restore_operator_context_clears_incompatible_role_or_session(tmp_path: Path, monkeypatch) -> None:
    context_file = tmp_path / "operator-context.json"
    monkeypatch.setenv("ARIS3_OPERATOR_CONTEXT_PATH", str(context_file))

    save_context(
        session_fingerprint="SUPERADMIN:tenant-1",
        selected_tenant_id="tenant-1",
        filters_by_module={"stores": {"q": "north"}},
        pagination_by_module={"stores": {"page": 2, "page_size": 20}},
    )

    incompatible = restore_compatible_context(session_fingerprint="MANAGER:tenant-9")

    assert incompatible == {}
    assert not context_file.exists()



class _StoresClientStub:
    def __init__(self, rows):
        self.rows = rows

    def list_stores(self, *_args, **_kwargs):
        return {"rows": self.rows, "page": 1, "page_size": 500, "total": len(self.rows), "has_next": False}


class _NoopClient:
    pass


def test_users_store_filter_cleared_when_store_not_in_active_tenant() -> None:
    from aris_control_2.app.admin_console import AdminConsole

    stores = _StoresClientStub(rows=[{"id": "store-a", "tenant_id": "tenant-a"}])
    console = AdminConsole(tenants=_NoopClient(), stores=stores, users=_NoopClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-a", selected_tenant_id="tenant-a")
    session.filters_by_module["users"] = {"store_id": "store-z", "status": "ACTIVE"}

    is_valid = console._ensure_users_store_filter_is_valid(session, "tenant-a")

    assert is_valid is False
    assert session.filters_by_module["users"] == {"status": "ACTIVE"}


def test_users_store_filter_kept_when_store_matches_active_tenant() -> None:
    from aris_control_2.app.admin_console import AdminConsole

    stores = _StoresClientStub(rows=[{"id": "store-a", "tenant_id": "tenant-a"}])
    console = AdminConsole(tenants=_NoopClient(), stores=stores, users=_NoopClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-a", selected_tenant_id="tenant-a")
    session.filters_by_module["users"] = {"store_id": "store-a", "status": "ACTIVE"}

    is_valid = console._ensure_users_store_filter_is_valid(session, "tenant-a")

    assert is_valid is True
    assert session.filters_by_module["users"]["store_id"] == "store-a"
