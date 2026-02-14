from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.load_me_use_case import LoadMeUseCase
from aris_control_2.app.application.use_cases.login_use_case import LoginUseCase
from aris_control_2.app.application.use_cases.select_tenant_use_case import SelectTenantUseCase
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.app.infrastructure.sdk_adapter.auth_adapter import AuthAdapter
from aris_control_2.app.ui.views.login_view import LoginView
from aris_control_2.app.ui.views.stores_view import StoresView
from aris_control_2.app.ui.views.tenants_view import TenantsView
from aris_control_2.app.ui.views.users_view import UsersView
from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


def build_shell() -> tuple[SessionState, LoginUseCase, LoadMeUseCase, SelectTenantUseCase, TenantsView, StoresView, UsersView]:
    http = HttpClient.from_env()
    auth_store = AuthStore()
    auth_adapter = AuthAdapter(http=http, auth_store=auth_store)
    admin_adapter = AdminAdapter(http=http, auth_store=auth_store)

    state = SessionState()
    return (
        state,
        LoginUseCase(auth_adapter=auth_adapter, state=state),
        LoadMeUseCase(auth_adapter=auth_adapter, state=state),
        SelectTenantUseCase(state=state),
        TenantsView(adapter=admin_adapter, state=state),
        StoresView(adapter=admin_adapter, state=state),
        UsersView(adapter=admin_adapter, state=state),
    )


def main() -> None:
    state, login_uc, me_uc, select_tenant_uc, tenants_view, stores_view, users_view = build_shell()

    credentials = LoginView().prompt_credentials()
    login_uc.execute(username_or_email=credentials[0], password=credentials[1])
    me_uc.execute()

    while True:
        print("\n=== ARIS Control 2 ===")
        print("1) Tenants")
        print("2) Stores")
        print("3) Users")
        print("4) Select tenant")
        print("0) Exit")
        option = input("> ").strip()

        if option == "1":
            tenants_view.render()
        elif option == "2":
            stores_view.render()
        elif option == "3":
            users_view.render()
        elif option == "4":
            tenant_id = input("Tenant ID: ").strip() or None
            select_tenant_uc.execute(tenant_id)
        elif option == "0":
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
