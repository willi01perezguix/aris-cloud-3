from aris_control_2.app.state import SessionState
from aris_control_2.app.ui.permission_map import check_permission


def test_permission_map_allows_admin_core_for_admin() -> None:
    session = SessionState(access_token="token", role="ADMIN")

    decision = check_permission(session, "menu.admin_core")

    assert decision.allowed is True


def test_permission_map_denies_tenant_switch_for_non_superadmin() -> None:
    session = SessionState(access_token="token", role="MANAGER")

    decision = check_permission(session, "menu.tenant_switch")

    assert decision.allowed is False
    assert decision.mode == "hidden"
