from __future__ import annotations


class TenantContextError(ValueError):
    pass


def is_superadmin(role: str | None) -> bool:
    return (role or "").strip().upper() == "SUPERADMIN"


def resolve_operational_tenant_id(role: str | None, effective_tenant_id: str | None, selected_tenant_id: str | None) -> str:
    resolved = resolve_tenant_context(role=role, session_tenant_id=effective_tenant_id, selected_tenant_id=selected_tenant_id)
    if not resolved[0]:
        raise TenantContextError(resolved[1])
    return resolved[0]


def resolve_tenant_context(*, role: str | None, session_tenant_id: str | None, selected_tenant_id: str | None) -> tuple[str | None, str]:
    if is_superadmin(role):
        if not selected_tenant_id:
            return None, "Debes seleccionar un tenant explícito para operar como SUPERADMIN."
        return selected_tenant_id, "SUPERADMIN con tenant explícito."

    if not session_tenant_id:
        return None, "No se pudo resolver el tenant de sesión/token para el rol actual."

    return session_tenant_id, "Tenant resuelto desde sesión/token."
