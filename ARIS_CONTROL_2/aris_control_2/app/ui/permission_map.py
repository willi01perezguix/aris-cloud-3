from __future__ import annotations

from dataclasses import dataclass

from aris_control_2.app.state import SessionState


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    mode: str
    message: str = ""


_PERMISSION_RULES: dict[str, dict[str, object]] = {
    "menu.me": {"roles": {"SUPERADMIN", "ADMIN", "MANAGER", "OPERATOR", "SUPPORT"}, "fallback_message": "Inicia sesión para ver /me."},
    "menu.admin_core": {"roles": {"SUPERADMIN", "ADMIN", "MANAGER", "OPERATOR"}, "fallback_message": "Tu rol no habilita Admin Core."},
    "menu.tenant_switch": {"roles": {"SUPERADMIN"}, "fallback_message": "Solo SUPERADMIN puede cambiar tenant activo."},
    "action.login": {"anonymous_only": True, "fallback_message": "Ya existe una sesión autenticada."},
    "action.logout": {"requires_auth": True, "fallback_message": "No hay sesión activa para cerrar."},
    "action.export_support": {"roles": {"SUPERADMIN", "ADMIN", "MANAGER", "OPERATOR", "SUPPORT"}, "fallback_message": "Sin permiso para exportar soporte."},
}


def check_permission(session: SessionState, key: str) -> PermissionDecision:
    rule = _PERMISSION_RULES.get(key)
    if rule is None:
        return PermissionDecision(False, "hidden", f"Permiso no mapeado: {key}.")

    requires_auth = bool(rule.get("requires_auth"))
    anonymous_only = bool(rule.get("anonymous_only"))
    roles = rule.get("roles")
    fallback_message = str(rule.get("fallback_message") or "Acción no permitida.")

    if anonymous_only:
        if session.is_authenticated():
            return PermissionDecision(False, "disabled", fallback_message)
        return PermissionDecision(True, "enabled")

    if requires_auth and not session.is_authenticated():
        return PermissionDecision(False, "disabled", fallback_message)

    if isinstance(roles, set):
        role = (session.role or "").upper()
        if role not in roles:
            return PermissionDecision(False, "hidden", fallback_message)

    if not session.is_authenticated() and key.startswith("menu."):
        return PermissionDecision(False, "disabled", "Inicia sesión para habilitar esta ruta protegida.")

    return PermissionDecision(True, "enabled")


__all__ = ["PermissionDecision", "check_permission"]
