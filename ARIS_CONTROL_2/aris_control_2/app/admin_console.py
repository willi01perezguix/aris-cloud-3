from __future__ import annotations

from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.idempotency import generate_idempotency_key
from clients.aris3_client_sdk.stores_client import StoresClient
from clients.aris3_client_sdk.tenants_client import TenantsClient
from clients.aris3_client_sdk.users_client import UsersClient

from aris_control_2.app.state import SessionState
from aris_control_2.app.tenant_context import TenantContextError, is_superadmin, resolve_operational_tenant_id


class AdminConsole:
    def __init__(self, tenants: TenantsClient, stores: StoresClient, users: UsersClient) -> None:
        self.tenants = tenants
        self.stores = stores
        self.users = users

    def run(self, session: SessionState) -> None:
        while True:
            print("\nAdmin Core")
            print("1. Seleccionar tenant (solo SUPERADMIN)")
            print("2. Listar tenants")
            print("3. Crear tenant (SUPERADMIN)")
            print("4. Listar stores (tenant operativo)")
            print("5. Crear store (tenant operativo)")
            print("6. Listar users (tenant operativo)")
            print("7. Crear user (tenant operativo + store válido)")
            print("8. Acción sobre user (set_role / set_status / reset_password)")
            print("9. Volver")
            option = input("Selecciona una opción: ").strip()

            try:
                if option == "1":
                    self._select_tenant(session)
                elif option == "2":
                    self._list_tenants(session)
                elif option == "3":
                    self._create_tenant(session)
                elif option == "4":
                    self._list_stores(session)
                elif option == "5":
                    self._create_store(session)
                elif option == "6":
                    self._list_users(session)
                elif option == "7":
                    self._create_user(session)
                elif option == "8":
                    self._user_action(session)
                elif option == "9":
                    return
                else:
                    print("Opción no válida.")
            except TenantContextError as error:
                print(f"Guardrail: {error}")
            except ApiError as error:
                _print_api_error(error)

    def _select_tenant(self, session: SessionState) -> None:
        if not is_superadmin(session.role):
            print("Solo SUPERADMIN puede seleccionar tenant. Se usa tenant efectivo del actor.")
            return
        tenant_id = input("tenant_id a seleccionar: ").strip()
        if not tenant_id:
            print("tenant_id es requerido.")
            return
        session.selected_tenant_id = tenant_id
        print(f"Tenant seleccionado: {tenant_id}")

    def _list_tenants(self, session: SessionState) -> None:
        self._require_superadmin(session)
        tenants = self.tenants.list_tenants(session.access_token or "")
        print(f"tenants={tenants}")

    def _create_tenant(self, session: SessionState) -> None:
        self._require_superadmin(session)
        code = input("code: ").strip()
        name = input("name: ").strip()
        if not code or not name:
            print("code y name son requeridos.")
            return
        payload = {"code": code, "name": name}
        result = self.tenants.create_tenant(session.access_token or "", payload, generate_idempotency_key())
        print(f"Tenant creado: {result}")

    def _list_stores(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        stores = self.stores.list_stores(session.access_token or "", tenant_id)
        print(f"stores={stores}")

    def _create_store(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        code = input("code: ").strip()
        name = input("name: ").strip()
        if not code or not name:
            print("code y name son requeridos.")
            return
        payload = {"tenant_id": tenant_id, "code": code, "name": name}
        created = self.stores.create_store(session.access_token or "", payload, generate_idempotency_key())
        print(f"Store creada: {created}")

    def _list_users(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        users = self.users.list_users(session.access_token or "", tenant_id)
        print(f"users={users}")

    def _create_user(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        username = input("username: ").strip()
        email = input("email: ").strip()
        role = input("role: ").strip().upper()
        password = input("password: ").strip()
        store_id = input("store_id: ").strip()
        if not username or not email or not role or not password or not store_id:
            print("username, email, role, password y store_id son requeridos.")
            return

        stores = self.stores.list_stores(session.access_token or "", tenant_id)
        store = next((item for item in stores if str(item.get("id")) == store_id), None)
        if not store:
            print("Guardrail: store_id no pertenece al tenant operativo. Operación cancelada.")
            return
        if str(store.get("tenant_id") or "") and str(store.get("tenant_id")) != tenant_id:
            print("Guardrail: mismatch tenant/store detectado. Operación cancelada.")
            return

        payload = {
            "tenant_id": tenant_id,
            "store_id": store_id,
            "username": username,
            "email": email,
            "role": role,
            "password": password,
        }
        created = self.users.create_user(session.access_token or "", payload, generate_idempotency_key())
        print(f"User creado: {created}")

    def _user_action(self, session: SessionState) -> None:
        self._resolve_tenant(session)
        user_id = input("user_id: ").strip()
        action = input("action [set_role|set_status|reset_password]: ").strip()
        payload = self._build_user_action_payload(action)
        if payload is None:
            return
        result = self.users.user_action(
            session.access_token or "",
            user_id=user_id,
            action=action,
            action_payload=payload,
            idempotency_key=generate_idempotency_key(),
        )
        print(f"Acción aplicada: {result}")

    def _build_user_action_payload(self, action: str) -> dict | None:
        if action == "set_role":
            role = input("new role: ").strip().upper()
            return {"role": role} if role else None
        if action == "set_status":
            status = input("new status: ").strip().upper()
            return {"status": status} if status else None
        if action == "reset_password":
            new_password = input("new_password: ").strip()
            return {"new_password": new_password} if new_password else None
        print("Acción no soportada.")
        return None

    def _resolve_tenant(self, session: SessionState) -> str:
        return resolve_operational_tenant_id(session.role, session.effective_tenant_id, session.selected_tenant_id)

    def _require_superadmin(self, session: SessionState) -> None:
        if not is_superadmin(session.role):
            raise TenantContextError("Operación permitida solo para SUPERADMIN.")


def _print_api_error(error: ApiError) -> None:
    print("Error de API:")
    print(f"  status_code: {error.status_code}")
    print(f"  code: {error.code}")
    print(f"  message: {error.message}")
    print(f"  trace_id: {error.trace_id}")
