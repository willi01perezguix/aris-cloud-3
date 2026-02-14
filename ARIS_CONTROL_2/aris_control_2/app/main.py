from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter

import httpx

from clients.aris3_client_sdk.auth_client import AuthClient
from clients.aris3_client_sdk.config import SDKConfig
from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.http_client import HttpClient
from clients.aris3_client_sdk.me_client import MeClient
from clients.aris3_client_sdk.stores_client import StoresClient
from clients.aris3_client_sdk.tenants_client import TenantsClient
from clients.aris3_client_sdk.users_client import UsersClient

from aris_control_2.app.admin_console import AdminConsole
from aris_control_2.app.context_store import (
    clear_auth_recovery_context,
    clear_context,
    load_auth_recovery_context,
    restore_compatible_context,
    save_auth_recovery_context,
    save_context,
)
from aris_control_2.app.diagnostics import APP_VERSION, ConnectivityResult, build_diagnostic_report, report_to_text, run_health_check
from aris_control_2.app.error_presenter import build_error_payload, print_error_banner
from aris_control_2.app.session_guard import SessionGuard
from aris_control_2.app.state import SessionState


def _print_runtime_config(config: SDKConfig, environment: str) -> None:
    print("ARIS_CONTROL_2")
    print(f"Base URL: {config.base_url}")
    print(f"Timeout: {config.timeout_seconds}s")
    print(f"Verify SSL: {config.verify_ssl}")
    print(f"Entorno: {environment}")
    print(f"Versión: {APP_VERSION}")


def _api_diagnostics(http_client: HttpClient) -> list[dict[str, str]]:
    checks: list[tuple[str, str]] = [("health", "/health"), ("ready", "/ready")]
    results: list[dict[str, str]] = []
    for name, path in checks:
        started = perf_counter()
        try:
            payload = http_client.request("GET", path)
            elapsed_ms = int((perf_counter() - started) * 1000)
            results.append({"check": name, "status": "OK", "latency_ms": str(elapsed_ms), "details": str(payload)})
        except ApiError as error:
            elapsed_ms = int((perf_counter() - started) * 1000)
            results.append(
                {
                    "check": name,
                    "status": "ERROR",
                    "latency_ms": str(elapsed_ms),
                    "details": f"{error.code} ({error.status_code}) trace_id={error.trace_id}",
                }
            )
    return results


def _print_connectivity(connectivity: ConnectivityResult | None) -> None:
    if connectivity is None:
        print("Conectividad API: no evaluada")
        return
    latency = f"{connectivity.latency_ms}ms" if connectivity.latency_ms is not None else "N/A"
    print(f"Conectividad API: {connectivity.status} ({latency})")


def _has_operational_permission(session: SessionState) -> bool:
    if not session.role:
        return False
    return session.role in {"SUPERADMIN", "ADMIN", "MANAGER", "OPERATOR", "SUPPORT"}


def _persist_operator_context(session: SessionState) -> None:
    if not session.role:
        return
    save_context(
        session_fingerprint=session.session_fingerprint(),
        selected_tenant_id=session.selected_tenant_id,
        filters_by_module=session.filters_by_module,
        pagination_by_module=session.pagination_by_module,
        listing_view_by_module=session.listing_view_by_module,
    )


def _restore_operator_context(session: SessionState) -> None:
    payload = restore_compatible_context(session_fingerprint=session.session_fingerprint())
    if not payload:
        return
    session.selected_tenant_id = payload.get("selected_tenant_id")
    restored_filters = payload.get("filters_by_module")
    if isinstance(restored_filters, dict):
        session.filters_by_module = {str(key): value for key, value in restored_filters.items() if isinstance(value, dict)}
    restored_pagination = payload.get("pagination_by_module")
    if isinstance(restored_pagination, dict):
        session.pagination_by_module = {
            str(key): value
            for key, value in restored_pagination.items()
            if isinstance(value, dict)
        }
    restored_listing_view = payload.get("listing_view_by_module")
    if isinstance(restored_listing_view, dict):
        session.listing_view_by_module = {
            str(key): value
            for key, value in restored_listing_view.items()
            if isinstance(value, dict)
        }


def _restore_auth_recovery_context(session: SessionState) -> None:
    payload = load_auth_recovery_context()
    if not payload:
        return

    if session.role != "SUPERADMIN" and session.selected_tenant_id and session.selected_tenant_id != session.effective_tenant_id:
        clear_auth_recovery_context()
        return

    session.current_module = str(payload.get("current_module") or session.current_module)
    recovered_tenant = payload.get("selected_tenant_id")
    if session.role == "SUPERADMIN" or recovered_tenant == session.effective_tenant_id:
        session.selected_tenant_id = recovered_tenant

    recovered_filters = payload.get("filters_by_module")
    if isinstance(recovered_filters, dict):
        session.filters_by_module = {str(key): value for key, value in recovered_filters.items() if isinstance(value, dict)}
    recovered_pagination = payload.get("pagination_by_module")
    if isinstance(recovered_pagination, dict):
        session.pagination_by_module = {
            str(key): value
            for key, value in recovered_pagination.items()
            if isinstance(value, dict)
        }
    recovered_listing_view = payload.get("listing_view_by_module")
    if isinstance(recovered_listing_view, dict):
        session.listing_view_by_module = {
            str(key): value
            for key, value in recovered_listing_view.items()
            if isinstance(value, dict)
        }
    clear_auth_recovery_context()


def _logout_session(session: SessionState, *, keep_recovery_context: bool = False) -> None:
    session.clear()
    if not keep_recovery_context:
        clear_auth_recovery_context()
    clear_context()


def _show_session_banner(*, reason: str, action: str, trace_id: str | None = None) -> None:
    safe_trace = trace_id or "n/a"
    message_by_reason = {
        "expired_token": "Tu sesión expiró. Vuelve a iniciar sesión para continuar.",
        "missing_token": "No hay sesión activa. Inicia sesión para acceder.",
        "corrupt_token": "Se detectó una sesión inválida. Debes autenticarte de nuevo.",
        "401": "Sesión inválida o expirada.",
        "403": "No tienes permisos para esta acción.",
    }
    code = "AUTH_FORBIDDEN" if reason == "403" else "AUTH_SESSION_INVALID"
    print(
        "[SESION] "
        f"code={code} "
        f"message={message_by_reason.get(reason, 'Error de sesión.')} "
        f"trace_id={safe_trace} "
        f"action={action}"
    )


def _copy_to_clipboard(text: str) -> bool:
    try:
        import tkinter  # noqa: PLC0415

        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False


def _show_diagnostics_panel(
    *,
    config: SDKConfig,
    environment: str,
    session: SessionState,
    connectivity: ConnectivityResult | None,
    last_error: dict | None,
    http_client: HttpClient,
) -> ConnectivityResult | None:
    if not _has_operational_permission(session):
        print("Diagnóstico disponible solo para roles operativos.")
        return connectivity

    while True:
        now = datetime.now().astimezone()
        print("\nDiagnóstico")
        print(f"  base_url_activa: {config.base_url}")
        print(f"  conectividad: {connectivity.status if connectivity else 'No evaluada'}")
        print(f"  app_version: {APP_VERSION}")
        print(f"  entorno: {environment}")
        print(f"  hora_local: {now.isoformat()}")
        print("Acciones: r=reintentar conexión, c=copiar diagnóstico, e=exportar reporte, b=volver")
        option = input("cmd diagnóstico: ").strip().lower()

        if option == "r":
            connectivity = run_health_check(http_client)
        elif option == "c":
            report = build_diagnostic_report(
                base_url=config.base_url,
                environment=environment,
                module=session.current_module,
                connectivity=connectivity,
                last_error=last_error,
            )
            text_report = report_to_text(report)
            copied = _copy_to_clipboard(text_report)
            print("Diagnóstico copiado." if copied else "No fue posible copiar al portapapeles en este entorno.")
        elif option == "e":
            report = build_diagnostic_report(
                base_url=config.base_url,
                environment=environment,
                module=session.current_module,
                connectivity=connectivity,
                last_error=last_error,
            )
            output_dir = Path("out") / "reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            stamp = now.strftime("%Y%m%d-%H%M%S")
            json_path = output_dir / f"diagnostico-{stamp}.json"
            txt_path = output_dir / f"diagnostico-{stamp}.txt"
            json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            txt_path.write_text(report_to_text(report), encoding="utf-8")
            print(f"Reporte exportado: {json_path} y {txt_path}")
        elif option == "b":
            return connectivity


def main() -> None:
    config = SDKConfig.from_env()
    environment = os.getenv("ARIS3_ENV", "dev").strip().lower() or "dev"
    http_client = HttpClient(config=config)
    auth_client = AuthClient(http_client)
    me_client = MeClient(http_client)
    session = SessionState()
    last_error: dict | None = None
    connectivity: ConnectivityResult | None = run_health_check(http_client)

    def _handle_invalid_session(reason: str) -> None:
        save_auth_recovery_context(
            reason=reason,
            current_module=session.current_module,
            selected_tenant_id=session.selected_tenant_id,
            filters_by_module=session.filters_by_module,
            pagination_by_module=session.pagination_by_module,
            listing_view_by_module=session.listing_view_by_module,
        )
        _logout_session(session, keep_recovery_context=True)
        _show_session_banner(reason=reason, action="Ir a login")

    session_guard = SessionGuard(on_invalid_session=_handle_invalid_session)

    def _handle_http_auth_error(error: ApiError) -> None:
        if error.status_code == 401:
            _handle_invalid_session("401")
            return
        if error.status_code == 403:
            _show_session_banner(reason="403", action="Volver al inicio", trace_id=error.trace_id)

    http_client.register_auth_error_handler(_handle_http_auth_error)

    admin_console = AdminConsole(
        TenantsClient(http_client),
        StoresClient(http_client),
        UsersClient(http_client),
        on_context_updated=lambda: _persist_operator_context(session),
    )

    _print_runtime_config(config, environment)
    _print_connectivity(connectivity)

    while True:
        print("\nMenú")
        print("1. Login")
        print("2. Ver /me")
        print("3. Admin Core")
        print("4. Logout")
        print("5. Exit")
        print("6. Diagnóstico API")
        option = input("Selecciona una opción: ").strip()

        try:
            if option == "1":
                username_or_email = input("username_or_email: ").strip()
                password = input("password: ").strip()
                response = auth_client.login(username_or_email=username_or_email, password=password)
                session.access_token = response.get("access_token")
                session.refresh_token = response.get("refresh_token")
                session.must_change_password = bool(response.get("must_change_password", False))
                _restore_auth_recovery_context(session)
                print("Login OK")
            elif option == "2":
                if not session_guard.require_session(session, module="me"):
                    continue
                me_payload = me_client.get_me(access_token=session.access_token or "")
                session.apply_me(me_payload)
                _restore_operator_context(session)
                _persist_operator_context(session)
                print(f"/me => {me_payload}")
            elif option == "3":
                if not session_guard.require_session(session, module="admin_core"):
                    continue
                admin_console.run(session)
            elif option == "4":
                _logout_session(session)
                print("Sesión cerrada.")
            elif option == "5":
                return
            elif option == "6":
                connectivity = _show_diagnostics_panel(
                    config=config,
                    environment=environment,
                    session=session,
                    connectivity=connectivity,
                    last_error=last_error,
                    http_client=http_client,
                )
            else:
                print("Opción no válida.")
        except ApiError as error:
            payload = build_error_payload(error)
            last_error = payload
            print_error_banner(payload)
        except httpx.HTTPError as error:
            payload = build_error_payload(error)
            last_error = payload
            print_error_banner(payload)
        except Exception as error:  # noqa: BLE001
            payload = build_error_payload(error)
            last_error = payload
            print_error_banner(payload)


if __name__ == "__main__":
    main()
