import pytest

from aris_control_2.app.tenant_context import TenantContextError, resolve_operational_tenant_id


def test_superadmin_requires_selected_tenant() -> None:
    with pytest.raises(TenantContextError):
        resolve_operational_tenant_id("SUPERADMIN", effective_tenant_id="tenant-1", selected_tenant_id=None)


def test_non_superadmin_forces_effective_tenant() -> None:
    tenant_id = resolve_operational_tenant_id("admin", effective_tenant_id="tenant-effective", selected_tenant_id="tenant-selected")

    assert tenant_id == "tenant-effective"
