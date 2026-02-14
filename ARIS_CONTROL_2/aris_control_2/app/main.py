from __future__ import annotations

from clients.aris3_client_sdk.auth_client import AuthClient
from clients.aris3_client_sdk.config import SDKConfig
from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.http_client import HttpClient
from clients.aris3_client_sdk.me_client import MeClient

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


def main() -> None:
    config = SDKConfig.from_env()
    http_client = HttpClient(config=config)
    auth_client = AuthClient(http_client)
    me_client = MeClient(http_client)
    session = SessionState()

    _print_runtime_config(config)

    while True:
        print("\nMenú")
        print("1. Login")
        print("2. Ver /me")
        print("3. Logout")
        print("4. Exit")
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
                session.user = me_payload
                print(f"/me => {me_payload}")
            elif option == "3":
                session.clear()
                print("Sesión cerrada.")
            elif option == "4":
                print("Hasta luego.")
                return
            else:
                print("Opción no válida.")
        except ApiError as error:
            _print_api_error(error)
        except Exception as error:  # noqa: BLE001
            print(f"Ocurrió un error inesperado: {error}")


if __name__ == "__main__":
    main()
