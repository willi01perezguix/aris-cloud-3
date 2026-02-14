from aris_control_2.app.admin_console import AdminConsole
from aris_control_2.app.state import SessionState
from aris_control_2.app.ui.listing_view import ColumnDef
from aris_control_2.app.ui.components.error_banner import ErrorBanner


class _StubClient:
    pass


def test_error_banner_unifies_string_format(capsys) -> None:
    ErrorBanner.show("falló validación")

    output = capsys.readouterr().out.strip()
    assert "code=UI_VALIDATION" in output
    assert "message=falló validación" in output
    assert "trace_id=n/a" in output


def test_admin_refresh_keeps_tenant_and_filters(monkeypatch, capsys) -> None:
    console = AdminConsole(tenants=_StubClient(), stores=_StubClient(), users=_StubClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-a", selected_tenant_id="tenant-a")
    session.filters_by_module["stores"] = {"q": "main", "status": "ACTIVE"}

    calls: list[tuple[int, int]] = []

    def fetch_page(page: int, page_size: int):
        calls.append((page, page_size))
        return {"rows": [{"id": "s1", "name": "Main", "status": "ACTIVE"}], "page": page, "page_size": page_size, "total": 1, "has_next": False}

    answers = iter(["", "r", "b"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    console._run_listing_loop(
        module="stores",
        session=session,
        fetch_page=fetch_page,
        columns=[ColumnDef("id", "id"), ColumnDef("name", "name"), ColumnDef("status", "status")],
        filter_keys=["q", "status"],
    )

    output = capsys.readouterr().out
    assert "[loading] Cargando stores" in output
    assert "[refresh] Recargando listado y preservando tenant/filtros/paginación activos..." in output
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert session.selected_tenant_id == "tenant-a"
    assert session.filters_by_module["stores"] == {"q": "main", "status": "ACTIVE"}


def test_admin_duplicate_filters_between_stores_and_users() -> None:
    console = AdminConsole(tenants=_StubClient(), stores=_StubClient(), users=_StubClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-a", selected_tenant_id="tenant-a")
    session.filters_by_module["stores"] = {"q": "north", "status": "ACTIVE", "extra": "ignored"}

    console._duplicate_related_filters(session, "stores")

    assert session.filters_by_module["users"] == {"q": "north", "status": "ACTIVE"}
    assert session.selected_tenant_id == "tenant-a"


def test_admin_validation_errors_are_unified_for_critical_forms(monkeypatch, capsys) -> None:
    console = AdminConsole(tenants=_StubClient(), stores=_StubClient(), users=_StubClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-a", selected_tenant_id="tenant-a")

    monkeypatch.setattr("builtins.input", lambda _: "")

    console._create_store(session)

    output = capsys.readouterr().out.strip()
    assert "code=UI_VALIDATION" in output
    assert "message=code y name son requeridos." in output
    assert "trace_id=n/a" in output


def test_admin_quick_access_shortcuts_open_target_listing(monkeypatch) -> None:
    console = AdminConsole(tenants=_StubClient(), stores=_StubClient(), users=_StubClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-a", selected_tenant_id="tenant-a")

    called: list[str] = []
    monkeypatch.setattr(console, "_list_tenants", lambda _session: called.append("tenants"))
    monkeypatch.setattr(console, "_list_stores", lambda _session: called.append("stores"))
    monkeypatch.setattr(console, "_list_users", lambda _session: called.append("users"))

    answers = iter(["t", "s", "u", "9"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    console.run(session)

    assert called == ["tenants", "stores", "users"]


def test_listing_loop_prints_clear_empty_and_error_status(monkeypatch, capsys) -> None:
    console = AdminConsole(tenants=_StubClient(), stores=_StubClient(), users=_StubClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-a", selected_tenant_id="tenant-a")

    def fetch_page(_page: int, _page_size: int):
        return {"rows": [], "page": 1, "page_size": 20, "total": 0, "has_next": False}

    answers = iter(["b"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    console._run_listing_loop(
        module="stores",
        session=session,
        fetch_page=fetch_page,
        columns=[ColumnDef("id", "id")],
        filter_keys=["q"],
    )

    out = capsys.readouterr().out
    assert "[loading] Cargando stores tenant=tenant-a" in out
    assert "[empty] STORES: sin resultados para los filtros actuales." in out
