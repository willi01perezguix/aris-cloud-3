from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.create_user_use_case import CreateUserUseCase
from aris_control_2.app.application.use_cases.list_stores_use_case import ListStoresUseCase
from aris_control_2.app.application.use_cases.list_users_use_case import ListUsersUseCase
from aris_control_2.app.application.use_cases.user_actions_use_case import UserActionsUseCase
from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.app.ui.components.error_banner import ErrorBanner
from aris_control_2.app.ui.components.permission_gate import PermissionGate


class UsersView:
    def __init__(
        self,
        list_use_case: ListUsersUseCase,
        create_use_case: CreateUserUseCase,
        actions_use_case: UserActionsUseCase,
        list_stores_use_case: ListStoresUseCase,
        state: SessionState,
    ) -> None:
        self.list_use_case = list_use_case
        self.create_use_case = create_use_case
        self.actions_use_case = actions_use_case
        self.list_stores_use_case = list_stores_use_case
        self.state = state

    def render(self) -> None:
        allowed, reason = PermissionGate.require_tenant_context(self.state.context)
        if not allowed:
            ErrorBanner.show(reason)
            return
        try:
            users = self.list_use_case.execute()
            stores = self.list_stores_use_case.execute()
            print("-- Users --")
            for user in users:
                print(f"{user.id} :: {user.email}")
            print("Stores disponibles para alta de usuario:")
            for store in stores:
                print(f"- {store.id} ({store.name})")

            option = input("Crear user? [s/N]: ").strip().lower()
            if option == "s":
                email = input("Email: ").strip()
                password = input("Password: ").strip()
                store_id = input("Store ID (opcional): ").strip() or None
                self.create_use_case.execute(email=email, password=password, store_id=store_id)
                print("User creado y listado refrescado.")

            if PermissionGate.can(self.state.context, "users.actions.write"):
                action = input("Acción user (set_status/set_role/reset_password/skip): ").strip()
                if action in {"set_status", "set_role", "reset_password"}:
                    user_id = input("User ID: ").strip()
                    payload_value = input("Valor (status/role/new_password): ").strip()
                    payload = (
                        {"status": payload_value}
                        if action == "set_status"
                        else {"role": payload_value}
                        if action == "set_role"
                        else {"new_password": payload_value}
                    )
                    self.actions_use_case.execute(user_id=user_id, action=action, payload=payload)
                    print("Acción aplicada y listado refrescado.")
        except Exception as error:
            payload = ErrorMapper.to_payload(error)
            if payload["code"] == "TENANT_STORE_MISMATCH":
                payload["message"] = "La tienda seleccionada no corresponde al tenant efectivo."
            ErrorBanner.show(payload)
