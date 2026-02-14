from aris_control_2.app.tenant_context import TenantContextError, resolve_operational_tenant_id


def test_superadmin_requires_selected_tenant() -> None:
    try:
        resolve_operational_tenant_id("SUPERADMIN", "tenant-effective", None)
        assert False, "Expected TenantContextError"
    except TenantContextError as exc:
        assert "seleccionar" in str(exc)


def test_non_superadmin_forces_effective_tenant() -> None:
    tenant_id = resolve_operational_tenant_id("ADMIN", "tenant-effective", "tenant-selected")

    assert tenant_id == "tenant-effective"
