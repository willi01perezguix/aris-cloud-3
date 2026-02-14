from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.select_tenant_use_case import SelectTenantUseCase


def test_tenant_switch_resets_dependent_state() -> None:
    state = SessionState()
    state.context.actor_role = "SUPERADMIN"
    state.context.selected_tenant_id = "tenant-a"
    state.context.refresh_effective_tenant()
    state.stores_cache = ["s1"]
    state.users_cache = ["u1"]
    state.stores_filter = "abc"
    state.selected_store_row = "s1"
    state.stores_page = 3

    SelectTenantUseCase(state).execute("tenant-b")

    assert state.context.effective_tenant_id == "tenant-b"
    assert state.stores_cache == []
    assert state.users_cache == []
    assert state.stores_filter == ""
    assert state.selected_store_row is None
    assert state.stores_page == 1
