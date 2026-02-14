from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.create_user_use_case import CreateUserUseCase
from aris_control_2.app.application.use_cases.list_stores_use_case import ListStoresUseCase
from aris_control_2.app.application.use_cases.list_users_use_case import ListUsersUseCase
from aris_control_2.app.application.use_cases.user_actions_use_case import UserActionsUseCase
from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.app.ui.components.error_banner import ErrorBanner
from aris_control_2.app.ui.components.permission_gate import PermissionGate


def validate_store_for_selected_tenant(selected_tenant_id: str | None, store_id: str | None, stores: list) -> tuple[bool, str]:
    if not store_id:
        return True, ""
    if not selected_tenant_id:
        return False, "Selecciona tenant antes de asignar store al usuario."
    matched_store = next((store for store in stores if store.id == store_id), None)
    if matched_store is None:
        return False, "La store seleccionada no existe dentro del tenant seleccionado."
    if matched_store.tenant_id != selected_tenant_id:
        return False, "Mismatch tenant↔store: la store no pertenece al tenant seleccionado."
    return True, ""


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
        if not self.state.context.selected_tenant_id:
            ErrorBanner.show("Debes seleccionar tenant antes de listar o crear users.")
            return
        tenant_gate = PermissionGate.require_tenant_context(self.state.context)
        if not tenant_gate.allowed:
            ErrorBanner.show(tenant_gate.reason)
            return
        view_gate = PermissionGate.check(self.state.context, "users.view")
        if not view_gate.allowed:
            ErrorBanner.show(view_gate.reason)
            return

        print(f"[loading] cargando users para tenant={self.state.context.selected_tenant_id}...")
        try:
            users = self.list_use_case.execute()
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
            return

        if not users:
            print("[empty] No hay usuarios para el tenant seleccionado.")
        else:
            print("[ready] -- Users --")
            for user in users:
                print(f"{user.id} :: {user.email}")

        create_gate = PermissionGate.check(self.state.context, "users.create")
        if create_gate.allowed and input("Crear user? [s/N]: ").strip().lower() == "s":
            try:
                stores = self.list_stores_use_case.execute()
            except Exception as error:
                ErrorBanner.show(ErrorMapper.to_payload(error))
                stores = []

            if stores:
                print("[ready] Stores disponibles para el tenant seleccionado:")
                for store in stores:
                    print(f"- {store.id} :: {store.name}")
            else:
                print("[empty] No hay stores disponibles para asociar al usuario.")

            email = input("Email: ").strip()
            password = input("Password: ").strip()
            store_id = input("Store ID (opcional): ").strip() or None
            valid_store, reason = validate_store_for_selected_tenant(
                self.state.context.selected_tenant_id,
                store_id,
                stores,
            )
            if not valid_store:
                ErrorBanner.show(reason)
                return
            self.state.selected_user_store_id = store_id

            print("[spinner] creando usuario...")
            try:
                result = self.create_use_case.execute(email=email, password=password, store_id=store_id)
                if result.get("status") == "already_processed":
                    print("Operación ya procesada previamente.")
                else:
                    print("Usuario creado correctamente.")
            except Exception as error:
                ErrorBanner.show(ErrorMapper.to_payload(error))
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
        try:
            result = self.actions_use_case.execute(user_id=user_id, action=action, payload=payload)
            if result.get("status") == "already_processed":
                print("Operación ya procesada previamente.")
            else:
                print("Acción aplicada correctamente.")
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
