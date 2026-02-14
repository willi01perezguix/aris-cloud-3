from aris_control_2.app.admin_console import AdminConsole
from aris_control_2.app.state import SessionState
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
        columns=[("id", "id"), ("name", "name"), ("status", "status")],
        filter_keys=["q", "status"],
    )

    output = capsys.readouterr().out
    assert "[loading] Cargando stores" in output
    assert "[refresh] Recargando listado y preservando tenant/filtros/paginación activos..." in output
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert session.selected_tenant_id == "tenant-a"
    assert session.filters_by_module["stores"] == {"q": "main", "status": "ACTIVE"}
