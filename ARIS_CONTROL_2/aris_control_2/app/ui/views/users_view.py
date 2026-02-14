from datetime import datetime
import json
from pathlib import Path

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
from aris_control_2.app.ui.forms import (
    FormStatus,
    build_form_state,
    map_api_validation_errors,
    validate_user_form,
)
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


def clear_user_selection(state: SessionState, reason: str) -> None:
    if not state.selected_user_rows:
        return
    state.selected_user_rows.clear()
    state.selected_user_rows_tenant_id = None
    print(f"[selection-reset] {reason}")


def validate_homogeneous_tenant_selection(*, selected_ids: list[str], users: list, tenant_id: str | None) -> tuple[bool, str]:
    if not selected_ids:
        return False, "Debes seleccionar al menos un user para acción masiva."
    if not tenant_id:
        return False, "Debes seleccionar tenant antes de usar acciones masivas."

    users_by_id = {user.id: user for user in users}
    for user_id in selected_ids:
        user = users_by_id.get(user_id)
        if user is None:
            return False, f"Selección inválida: user {user_id} no existe en la vista actual."
        if user.tenant_id != tenant_id:
            return False, f"Selección inválida: user {user_id} pertenece a otro tenant."
    return True, ""


def summarize_bulk_results(results: list[dict]) -> dict:
    total = len(results)
    success = sum(1 for item in results if item.get("result") == "success")
    failed = total - success
    return {"total": total, "success": success, "failed": failed}


def export_bulk_results(results: list[dict], export_format: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("ARIS_CONTROL_2/out/day3")
    output_dir.mkdir(parents=True, exist_ok=True)
    if export_format == "json":
        output_path = output_dir / f"bulk_users_result_{timestamp}.json"
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path

    output_path = output_dir / f"bulk_users_result_{timestamp}.txt"
    lines = []
    for item in results:
        lines.append(
            " | ".join(
                [
                    f"user_id={item.get('user_id')}",
                    f"result={item.get('result')}",
                    f"code={item.get('code', 'n/a')}",
                    f"message={item.get('message', 'n/a')}",
                    f"trace_id={item.get('trace_id', 'n/a')}",
                ]
            )
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


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


def validate_user_action_context(
    *,
    selected_tenant_id: str | None,
    effective_tenant_id: str | None,
    action_gate_allowed: bool,
    action_gate_reason: str,
    user_id: str,
    action: str,
    payload: dict,
    users: list,
) -> tuple[bool, str]:
    if not action_gate_allowed:
        return False, action_gate_reason
    if not selected_tenant_id:
        return False, "Acción bloqueada: debes seleccionar tenant antes de ejecutar acciones administrativas."
    if effective_tenant_id != selected_tenant_id:
        return False, "Acción bloqueada: contexto tenant inconsistente, recarga sesión y vuelve a intentar."
    if not user_id:
        return False, "Acción bloqueada: user_id es requerido."

    target_user = next((user for user in users if user.id == user_id), None)
    if target_user is None:
        return False, "Acción bloqueada: el usuario objetivo no existe en la lista del tenant activo."
    if target_user.tenant_id != effective_tenant_id:
        return False, "Acción bloqueada: mismatch tenant, el usuario objetivo no pertenece al tenant efectivo."

    if action in {"set_status", "set_role", "reset_password"}:
        required_key = "status" if action == "set_status" else "role" if action == "set_role" else "new_password"
        if not payload.get(required_key):
            return False, f"Acción bloqueada: falta {required_key} para {action}."
    return True, ""


def render_last_admin_action(state: SessionState) -> None:
    if not state.last_admin_action:
        return
    last = state.last_admin_action
    print(
        "[audit] última acción "
        f"type={last.get('action')} "
        f"timestamp={last.get('timestamp_local')} "
        f"result={last.get('result')} "
        f"trace_id={last.get('trace_id', 'n/a')}"
    )


def _save_last_admin_action(state: SessionState, action: str, result: str, trace_id: str | None = None) -> None:
    state.last_admin_action = {
        "action": action,
        "timestamp_local": datetime.now().isoformat(timespec="seconds"),
        "result": result,
        "trace_id": trace_id or "n/a",
    }


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
        if self.state.selected_user_rows_tenant_id and self.state.selected_user_rows_tenant_id != self.state.context.selected_tenant_id:
            clear_user_selection(self.state, "Cambio de tenant detectado: selección limpiada para evitar ambigüedad.")

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
                marker = "[x]" if user.id in self.state.selected_user_rows else "[ ]"
                print(f"{marker} {user.id} :: {user.email}")
        print(f"[tenant-context] tenant={self.state.context.selected_tenant_id}")
        print(f"[selection] seleccionados={len(self.state.selected_user_rows)}")
        render_last_admin_action(self.state)

        action_option = input(
            "Acción users [r=refresh, f=filtro, p=page, m=multi-select, c=crear, a=acción, b=bulk, Enter=volver]: "
        ).strip().lower()
        if action_option == "r":
            print("[refresh] recargando users y manteniendo tenant/filtros activos...")
            self.render()
            return
        if action_option == "f":
            next_filter = input("Nuevo filtro users (vacío=sin filtro): ").strip()
            if next_filter != self.state.users_filter:
                self.state.users_filter = next_filter
                clear_user_selection(self.state, "Cambio de filtros: selección limpiada.")
            self.render()
            return
        if action_option == "p":
            next_page_raw = input("Página users: ").strip()
            if next_page_raw.isdigit() and int(next_page_raw) > 0 and int(next_page_raw) != self.state.users_page:
                self.state.users_page = int(next_page_raw)
                clear_user_selection(self.state, "Cambio de paginación: selección limpiada.")
            self.render()
            return
        if action_option == "m":
            selected_raw = input("IDs users separados por coma: ").strip()
            selected_ids = [item.strip() for item in selected_raw.split(",") if item.strip()]
            valid_selection, reason = validate_homogeneous_tenant_selection(
                selected_ids=selected_ids,
                users=users,
                tenant_id=self.state.context.selected_tenant_id,
            )
            if not valid_selection:
                print(f"[blocked] {reason}")
                return
            self.state.selected_user_rows = selected_ids
            self.state.selected_user_rows_tenant_id = self.state.context.selected_tenant_id
            print(f"[selection] {len(selected_ids)} users seleccionados")
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
            password = input("Password (mínimo 8 caracteres): ").strip()
            store_id = input("Store ID (opcional): ").strip() or None
            form_result = validate_user_form(
                email=email,
                password=password,
                tenant_id=self.state.context.selected_tenant_id,
                store_id=store_id,
            )
            form_state = build_form_state(form_result)
            if not form_state.submit_enabled:
                print(f"[disabled] Submit user ({form_state.submit_disabled_reason})")
                if form_result.first_invalid_field:
                    print(f"[focus] Corrige primero: {form_result.first_invalid_field}")
                for field_name, field_error in form_result.field_errors.items():
                    print(f"[field-error] {field_name}: {field_error}")
                return
            valid_store, reason = validate_store_for_selected_tenant(
                self.state.context.selected_tenant_id,
                form_result.values["store_id"],
                stores,
            )
            if not valid_store:
                print("[disabled] Submit user (store fuera de tenant contexto)")
                print("[focus] Corrige primero: store_id")
                ErrorBanner.show(reason)
                return
            self.state.selected_user_store_id = form_result.values["store_id"]

            create_operation = "user-create"
            if not begin_mutation(self.state, create_operation):
                print("[loading] Procesando… evita doble submit.")
                return
            form_state.status = FormStatus.SUBMITTING
            print("[loading] Procesando… (crear usuario)")
            try:
                attempt = get_or_create_attempt(self.state, create_operation)
                result = self.create_use_case.execute(
                    email=form_result.values["email"],
                    password=form_result.values["password"],
                    store_id=form_result.values["store_id"],
                    idempotency_key=attempt.idempotency_key,
                    transaction_id=attempt.transaction_id,
                )
                if result.get("status") == "already_processed":
                    print("Operación ya procesada previamente.")
                else:
                    print_mutation_success("user.create", result, highlighted_id=result.get("id"))
                form_state.status = FormStatus.SUCCESS
                clear_attempt(self.state, create_operation)
                print("[refresh] recargando users...")
                for user in self.list_use_case.execute():
                    marker = " <- actualizado" if result.get("id") and user.id == result.get("id") else ""
                    print(f"{user.id} :: {user.email}{marker}")
            except APIError as error:
                form_state.status = FormStatus.ERROR
                if error.status_code == 422:
                    field_errors = map_api_validation_errors(error.details)
                    for field_name, field_error in field_errors.items():
                        print(f"[field-error] {field_name}: {field_error}")
                print_mutation_error("user.create", error)
                ErrorBanner.show(ErrorMapper.to_payload(error))
                if input("Reintentar create user? [s/N]: ").strip().lower() == "s":
                    self.render()
            except Exception as error:
                form_state.status = FormStatus.ERROR
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

        if action_option == "b":
            if not self.state.selected_user_rows:
                print("[blocked] No hay users seleccionados para acción masiva.")
                return
            valid_selection, reason = validate_homogeneous_tenant_selection(
                selected_ids=self.state.selected_user_rows,
                users=users,
                tenant_id=self.state.context.selected_tenant_id,
            )
            if not valid_selection:
                print(f"[blocked] {reason}")
                return
            bulk_action = input("Acción masiva (set_status/skip): ").strip()
            if bulk_action != "set_status":
                return
            bulk_value = input("Nuevo status para lote: ").strip()
            payload = {"status": bulk_value}
            print("Resumen de acción masiva:")
            print(f"- tenant efectivo: {self.state.context.effective_tenant_id}")
            print(f"- acción: {bulk_action}")
            print(f"- afectados: {len(self.state.selected_user_rows)}")
            if input("Confirmar acción masiva? [s/N]: ").strip().lower() != "s":
                print("Acción masiva cancelada.")
                return

            chunk_size_raw = input("Chunk size (default=1): ").strip()
            chunk_size = int(chunk_size_raw) if chunk_size_raw.isdigit() and int(chunk_size_raw) > 0 else 1
            results: list[dict] = []
            total = len(self.state.selected_user_rows)
            action_operation = f"user-bulk-{bulk_action}"
            if not begin_mutation(self.state, action_operation):
                print("[loading] Procesando… evita doble submit.")
                return
            try:
                for start in range(0, total, chunk_size):
                    chunk_ids = self.state.selected_user_rows[start : start + chunk_size]
                    for user_id in chunk_ids:
                        progress = len(results) + 1
                        print(f"[bulk-progress] {progress}/{total} user={user_id}")
                        try:
                            attempt = get_or_create_attempt(self.state, f"{action_operation}-{user_id}")
                            result = self.actions_use_case.execute(
                                user_id=user_id,
                                action=bulk_action,
                                payload=payload,
                                idempotency_key=attempt.idempotency_key,
                                transaction_id=attempt.transaction_id,
                            )
                            clear_attempt(self.state, f"{action_operation}-{user_id}")
                            results.append(
                                {
                                    "user_id": user_id,
                                    "result": "success",
                                    "code": result.get("status", "ok"),
                                    "message": "processed",
                                    "trace_id": result.get("trace_id") or result.get("transaction_id"),
                                }
                            )
                        except APIError as error:
                            results.append(
                                {
                                    "user_id": user_id,
                                    "result": "error",
                                    "code": error.code,
                                    "message": error.message,
                                    "trace_id": error.trace_id,
                                }
                            )
                summary = summarize_bulk_results(results)
                print(
                    f"[bulk-summary] total={summary['total']} success={summary['success']} failed={summary['failed']}"
                )
                for item in results:
                    if item["result"] == "error":
                        print(
                            "[bulk-error] "
                            f"user_id={item['user_id']} code={item['code']} "
                            f"message={item['message']} trace_id={item.get('trace_id')}"
                        )
                export_choice = input("Exportar resultado? [txt/json/N]: ").strip().lower()
                if export_choice in {"txt", "json"}:
                    export_path = export_bulk_results(results, export_choice)
                    print(f"[export] Resultado exportado: {export_path}")
                print("[refresh] actualizando lista afectada sin perder contexto...")
                refreshed_users = self.list_use_case.execute()
                selected_ids = set(self.state.selected_user_rows)
                for user in refreshed_users:
                    marker = " <- actualizado" if user.id in selected_ids else ""
                    print(f"{user.id} :: {user.email}{marker}")
            finally:
                end_mutation(self.state, action_operation)
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
        valid_action, block_reason = validate_user_action_context(
            selected_tenant_id=self.state.context.selected_tenant_id,
            effective_tenant_id=self.state.context.effective_tenant_id,
            action_gate_allowed=actions_gate.allowed,
            action_gate_reason=actions_gate.reason,
            user_id=user_id,
            action=action,
            payload=payload,
            users=users,
        )
        if not valid_action:
            print(f"[blocked] {block_reason}")
            return
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
            _save_last_admin_action(
                self.state,
                action=f"user.{action}",
                result="OK",
                trace_id=result.get("trace_id") or result.get("transaction_id"),
            )
            clear_attempt(self.state, action_operation)
            print("[refresh] actualizando lista afectada sin perder contexto...")
            refreshed_users = self.list_use_case.execute()
            for user in refreshed_users:
                marker = " <- actualizado" if user.id == user_id else ""
                print(f"{user.id} :: {user.email}{marker}")
        except APIError as error:
            print_mutation_error(f"user.{action}", error)
            _save_last_admin_action(self.state, action=f"user.{action}", result="ERROR", trace_id=error.trace_id)
            ErrorBanner.show(ErrorMapper.to_payload(error))
            if input("Reintentar acción? [s/N]: ").strip().lower() == "s":
                self.render()
        except Exception as error:
            _save_last_admin_action(self.state, action=f"user.{action}", result="ERROR")
            ErrorBanner.show(ErrorMapper.to_payload(error))
            if input("Reintentar acción? [s/N]: ").strip().lower() == "s":
                self.render()
        finally:
            end_mutation(self.state, action_operation)
