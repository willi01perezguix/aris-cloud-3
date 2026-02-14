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
        tenant_gate = PermissionGate.require_tenant_context(self.state.context)
        if not tenant_gate.allowed:
            ErrorBanner.show(tenant_gate.reason)
            return
        view_gate = PermissionGate.check(self.state.context, "users.view")
        if not view_gate.allowed:
            ErrorBanner.show(view_gate.reason)
            return

        print("[loading] cargando users...")
        try:
            users = self.list_use_case.execute()
            if not users:
                print("[empty] No hay usuarios para el tenant actual.")
            else:
                print("[ready] -- Users --")
                for user in users:
                    print(f"{user.id} :: {user.email}")

            create_gate = PermissionGate.check(self.state.context, "users.create")
            if create_gate.allowed and input("Crear user? [s/N]: ").strip().lower() == "s":
                email = input("Email: ").strip()
                password = input("Password: ").strip()
                store_id = input("Store ID (opcional): ").strip() or None
                print("[spinner] creando usuario...")
                result = self.create_use_case.execute(email=email, password=password, store_id=store_id)
                if result.get("status") == "already_processed":
                    print("Operación ya procesada previamente.")
                else:
                    print("Usuario creado correctamente.")
            elif not create_gate.allowed:
                print(f"[disabled] Crear usuario ({create_gate.reason})")

            actions_gate = PermissionGate.check(self.state.context, "users.actions")
            if not actions_gate.allowed:
                print(f"[disabled] Acciones de usuario ({actions_gate.reason})")
                return

            action = input("Acción user (set_status/set_role/reset_password/skip): ").strip()
            if action not in {"set_status", "set_role", "reset_password"}:
                return
            if input(f"Confirmar acción {action}? [s/N]: ").strip().lower() != "s":
                print("Acción cancelada.")
                return
            user_id = input("User ID: ").strip()
            payload_value = input("Valor (status/role/new_password): ").strip()
            payload = (
                {"status": payload_value}
                if action == "set_status"
                else {"role": payload_value}
                if action == "set_role"
                else {"new_password": payload_value}
            )
            print("[spinner] aplicando acción...")
            result = self.actions_use_case.execute(user_id=user_id, action=action, payload=payload)
            if result.get("status") == "already_processed":
                print("Operación ya procesada previamente.")
            else:
                print("Acción aplicada correctamente.")
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
