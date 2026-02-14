from __future__ import annotations


class TenantContextError(ValueError):
    pass


def is_superadmin(role: str | None) -> bool:
    return (role or "").strip().upper() == "SUPERADMIN"


def resolve_operational_tenant_id(role: str | None, effective_tenant_id: str | None, selected_tenant_id: str | None) -> str:
    if is_superadmin(role):
        if not selected_tenant_id:
            raise TenantContextError(
                "Debes seleccionar un tenant para operar stores/users como SUPERADMIN."
            )
        return selected_tenant_id

    if not effective_tenant_id:
        raise TenantContextError("No se pudo resolver el tenant efectivo del actor autenticado.")
    return effective_tenant_id
