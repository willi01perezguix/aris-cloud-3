from aris_control_2.app.feature_flags import ClientFeatureFlags
from aris_control_2.app.navigation_shell import resolve_route
from aris_control_2.app.state import SessionState


def test_protected_route_blocks_admin_core_without_auth() -> None:
    allowed, message = resolve_route("3", SessionState(), ClientFeatureFlags())

    assert allowed is False
    assert "Admin Core" in message


def test_route_respects_feature_flag_for_diagnostics() -> None:
    flags = ClientFeatureFlags(diagnostics_module_enabled=False)
    session = SessionState(access_token="token", role="ADMIN")

    allowed, message = resolve_route("6", session, flags)

    assert allowed is False
    assert "feature flag" in message
