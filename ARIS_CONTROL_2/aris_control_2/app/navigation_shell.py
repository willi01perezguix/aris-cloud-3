from __future__ import annotations

from dataclasses import dataclass

from aris_control_2.app.diagnostics import ConnectivityResult
from aris_control_2.app.feature_flags import ClientFeatureFlags
from aris_control_2.app.state import SessionState
from aris_control_2.app.ui.permission_map import check_permission


@dataclass(frozen=True)
class NavRoute:
    key: str
    option: str
    label: str


ROUTES: list[NavRoute] = [
    NavRoute("action.login", "1", "Login"),
    NavRoute("menu.me", "2", "Ver /me"),
    NavRoute("menu.admin_core", "3", "Admin Core"),
    NavRoute("action.logout", "4", "Logout"),
    NavRoute("diagnostics", "6", "Diagnóstico API"),
    NavRoute("incidents", "7", "Incidencias"),
    NavRoute("action.export_support", "8", "Exportar paquete de soporte"),
    NavRoute("action.export_support", "9", "Copiar resumen técnico"),
]


def resolve_route(option: str, session: SessionState, flags: ClientFeatureFlags) -> tuple[bool, str]:
    if option == "0":
        return True, ""
    if option == "5":
        return True, ""

    route = next((item for item in ROUTES if item.option == option), None)
    if route is None:
        return False, "Opción no válida."

    if route.key == "diagnostics" and not flags.diagnostics_module_enabled:
        return False, "Diagnóstico deshabilitado por feature flag v1.1.0."
    if route.key == "incidents" and not flags.incidents_module_enabled:
        return False, "Incidencias deshabilitado por feature flag v1.1.0."

    decision = check_permission(session, route.key)
    if decision.allowed:
        return True, ""
    return False, decision.message


def render_shell(*, session: SessionState, connectivity: ConnectivityResult | None, flags: ClientFeatureFlags) -> None:
    if not flags.navigation_shell_v110:
        return

    connection_label = "No evaluada"
    if connectivity is not None:
        connection_label = connectivity.status

    print("\n=== ARIS Control v1.1.0 Shell ===")
    print(f"Header | conexión={connection_label} | tenant_activo={session.selected_tenant_id or session.effective_tenant_id or 'N/A'}")
    print(
        "Contexto | "
        f"tenant={session.selected_tenant_id or session.effective_tenant_id or 'N/A'} | "
        f"store=N/A | "
        f"rol={session.role or 'N/A'} | "
        f"conectividad={connection_label}"
    )
    print("Sidebar:")

    for route in ROUTES:
        if route.key == "diagnostics" and not flags.diagnostics_module_enabled:
            continue
        if route.key == "incidents" and not flags.incidents_module_enabled:
            continue
        decision = check_permission(session, route.key)
        if decision.mode == "hidden":
            continue
        suffix = "" if decision.allowed else f" [deshabilitado: {decision.message}]"
        print(f"  {route.option}. {route.label}{suffix}")

    if flags.tenant_switcher_v110:
        tenant_switch = check_permission(session, "menu.tenant_switch")
        if tenant_switch.allowed:
            print("  t. Cambiar tenant (rápido)")
        else:
            print(f"  t. Cambiar tenant (bloqueado: {tenant_switch.message})")

    print("  0. Reintentar startup check")
    print("  5. Exit")

