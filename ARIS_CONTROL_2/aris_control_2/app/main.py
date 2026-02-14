from __future__ import annotations

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
from aris_control_2.app.state import SessionState


def _print_runtime_config(config: SDKConfig) -> None:
    print("ARIS_CONTROL_2")
    print(f"Base URL: {config.base_url}")
    print(f"Timeout: {config.timeout_seconds}s")
    print(f"Verify SSL: {config.verify_ssl}")


def _print_api_error(error: ApiError) -> None:
    print("Error de API:")
    print(f"  status_code: {error.status_code}")
    print(f"  code: {error.code}")
    print(f"  message: {error.message}")
    print(f"  trace_id: {error.trace_id}")


def _api_diagnostics(http_client: HttpClient) -> list[dict[str, str]]:
    checks: list[tuple[str, str]] = [
        ("health", "/health"),
        ("ready", "/ready"),
    ]
    results: list[dict[str, str]] = []
    for name, path in checks:
        started = perf_counter()
        try:
            payload = http_client.request("GET", path)
            elapsed_ms = int((perf_counter() - started) * 1000)
            results.append(
                {
                    "check": name,
                    "status": "OK",
                    "latency_ms": str(elapsed_ms),
                    "details": str(payload) if payload else "sin payload",
                }
            )
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


def _print_api_connectivity_status(http_client: HttpClient) -> None:
    try:
        started = perf_counter()
        http_client.request("GET", "/health")
        elapsed_ms = int((perf_counter() - started) * 1000)
        print(f"Conectividad API: OK ({elapsed_ms}ms)")
    except ApiError as error:
        print(f"Conectividad API: ERROR ({error.code})")


def _print_api_diagnostics(http_client: HttpClient) -> None:
    print("\nDiagnóstico API")
    for result in _api_diagnostics(http_client):
        symbol = "✅" if result["status"] == "OK" else "❌"
        print(f"{symbol} {result['check']} [{result['latency_ms']}ms] -> {result['details']}")


def main() -> None:
    config = SDKConfig.from_env()
    http_client = HttpClient(config=config)
    auth_client = AuthClient(http_client)
    me_client = MeClient(http_client)
    admin_console = AdminConsole(TenantsClient(http_client), StoresClient(http_client), UsersClient(http_client))
    session = SessionState()

    _print_runtime_config(config)
    _print_api_connectivity_status(http_client)

    while True:
        print("\nMenú")
        print("1. Login")
        print("2. Ver /me")
        print("3. Admin Core")
        print("4. Logout")
        print("5. Exit")
        print("6. Diagnóstico de conectividad API")
        option = input("Selecciona una opción: ").strip()

        try:
            if option == "1":
                username_or_email = input("username_or_email: ").strip()
                password = input("password: ").strip()
                response = auth_client.login(username_or_email=username_or_email, password=password)
                session.access_token = response.get("access_token")
                session.refresh_token = response.get("refresh_token")
                session.must_change_password = bool(response.get("must_change_password", False))
                print("Login OK")
                if session.must_change_password:
                    print("Aviso: must_change_password=True")
            elif option == "2":
                if not session.is_authenticated():
                    print("Debes iniciar sesión primero.")
                    continue
                me_payload = me_client.get_me(access_token=session.access_token or "")
                session.apply_me(me_payload)
                print(f"/me => {me_payload}")
            elif option == "3":
                if not session.is_authenticated():
                    print("Debes iniciar sesión primero.")
                    continue
                admin_console.run(session)
            elif option == "4":
                session.clear()
                print("Sesión cerrada.")
            elif option == "5":
                print("Hasta luego.")
                return
            elif option == "6":
                _print_api_diagnostics(http_client)
            else:
                print("Opción no válida.")
        except ApiError as error:
            _print_api_error(error)
        except httpx.HTTPError as error:
            print(f"Error de red no controlado durante diagnóstico: {error}")
        except Exception as error:  # noqa: BLE001
            print(f"Ocurrió un error inesperado: {error}")


if __name__ == "__main__":
    main()
