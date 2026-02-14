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
