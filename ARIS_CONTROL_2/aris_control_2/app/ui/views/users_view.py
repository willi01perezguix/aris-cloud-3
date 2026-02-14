from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.mutation_attempts import (
    begin_mutation,
    clear_attempt,
    end_mutation,
    get_or_create_attempt,
)
from aris_control_2.app.application.use_cases.create_user_use_case import CreateUserUseCase
from aris_control_2.app.application.use_cases.list_stores_use_case import ListStoresUseCase
from aris_control_2.app.application.use_cases.list_users_use_case import ListUsersUseCase
from aris_control_2.app.application.use_cases.user_actions_use_case import UserActionsUseCase
from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.app.ui.components.error_banner import ErrorBanner
from aris_control_2.app.ui.components.mutation_feedback import print_mutation_error, print_mutation_success
from aris_control_2.app.ui.components.permission_gate import PermissionGate
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


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


def build_sensitive_action_summary(action: str, user_id: str, payload: dict, tenant_id: str | None) -> str:
    return (
        "Resumen de operación:\n"
        f"- acción: {action}\n"
        f"- user_id: {user_id}\n"
        f"- tenant: {tenant_id or 'N/A'}\n"
        f"- cambios: {payload}"
    )


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

        action_option = input("Acción users [r=refresh, c=crear, a=acciones, Enter=volver]: ").strip().lower()
        if action_option == "r":
            print("[refresh] recargando users y manteniendo tenant/filtros activos...")
            self.render()
            return

        create_gate = PermissionGate.check(self.state.context, "users.create")
        if create_gate.allowed and action_option in {"c", "s"}:
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

            create_operation = "user-create"
            if not begin_mutation(self.state, create_operation):
                print("[loading] Procesando… evita doble submit.")
                return
            print("[loading] Procesando… (crear usuario)")
            try:
                attempt = get_or_create_attempt(self.state, create_operation)
                result = self.create_use_case.execute(
                    email=email,
                    password=password,
                    store_id=store_id,
                    idempotency_key=attempt.idempotency_key,
                    transaction_id=attempt.transaction_id,
                )
                if result.get("status") == "already_processed":
                    print("Operación ya procesada previamente.")
                else:
                    print_mutation_success("user.create", result, highlighted_id=result.get("id"))
                clear_attempt(self.state, create_operation)
                print("[refresh] recargando users...")
                for user in self.list_use_case.execute():
                    marker = " <- actualizado" if result.get("id") and user.id == result.get("id") else ""
                    print(f"{user.id} :: {user.email}{marker}")
            except APIError as error:
                print_mutation_error("user.create", error)
                ErrorBanner.show(ErrorMapper.to_payload(error))
                if input("Reintentar create user? [s/N]: ").strip().lower() == "s":
                    self.render()
            except Exception as error:
                ErrorBanner.show(ErrorMapper.to_payload(error))
                if input("Reintentar create user? [s/N]: ").strip().lower() == "s":
                    self.render()
            finally:
                end_mutation(self.state, create_operation)
        elif action_option in {"c", "s"} and not create_gate.allowed:
            print(f"[disabled] Crear usuario ({create_gate.reason})")

        actions_gate = PermissionGate.check(self.state.context, "users.actions")
        if not actions_gate.allowed:
            print(f"[disabled] Acciones de usuario ({actions_gate.reason})")
            return

        if action_option not in {"a", ""}:
            return

        action = input("Acción user (set_status/set_role/reset_password/skip): ").strip()
        if action not in {"set_status", "set_role", "reset_password"}:
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
        print(build_sensitive_action_summary(action, user_id, payload, self.state.context.effective_tenant_id))
        if input(f"Confirmar acción sensible {action}? [s/N]: ").strip().lower() != "s":
            print("Acción cancelada.")
            return
        action_operation = f"user-action-{action}"
        if not begin_mutation(self.state, action_operation):
            print("[loading] Procesando… evita doble submit.")
            return
        print("[loading] Procesando… (acción usuario)")
        try:
            attempt = get_or_create_attempt(self.state, action_operation)
            result = self.actions_use_case.execute(
                user_id=user_id,
                action=action,
                payload=payload,
                idempotency_key=attempt.idempotency_key,
                transaction_id=attempt.transaction_id,
            )
            if result.get("status") == "already_processed":
                print("Operación ya procesada previamente.")
            else:
                print_mutation_success(f"user.{action}", result, highlighted_id=user_id)
            clear_attempt(self.state, action_operation)
            print("[refresh] recargando users...")
            for user in self.list_use_case.execute():
                marker = " <- actualizado" if user.id == user_id else ""
                print(f"{user.id} :: {user.email}{marker}")
        except APIError as error:
            print_mutation_error(f"user.{action}", error)
            ErrorBanner.show(ErrorMapper.to_payload(error))
            if input("Reintentar acción? [s/N]: ").strip().lower() == "s":
                self.render()
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
            if input("Reintentar acción? [s/N]: ").strip().lower() == "s":
                self.render()
        finally:
            end_mutation(self.state, action_operation)
