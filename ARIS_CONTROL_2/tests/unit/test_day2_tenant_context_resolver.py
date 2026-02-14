from aris_control_2.app.tenant_context import resolve_tenant_context


def test_tenant_context_resolver_uses_explicit_tenant_for_superadmin() -> None:
    tenant_id, reason = resolve_tenant_context(role="SUPERADMIN", session_tenant_id=None, selected_tenant_id="tenant-1")

    assert tenant_id == "tenant-1"
    assert "explícito" in reason


def test_tenant_context_resolver_uses_session_tenant_for_admin() -> None:
    tenant_id, reason = resolve_tenant_context(role="ADMIN", session_tenant_id="tenant-2", selected_tenant_id="tenant-x")

    assert tenant_id == "tenant-2"
    assert "sesión" in reason
