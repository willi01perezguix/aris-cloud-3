from aris_control_2.app.domain.models.store import Store
from aris_control_2.app.domain.models.tenant import Tenant
from aris_control_2.app.domain.models.user import User
from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient
from aris_control_2.clients.aris3_client_sdk.modules.stores_client import StoresClient
from aris_control_2.clients.aris3_client_sdk.modules.tenants_client import TenantsClient
from aris_control_2.clients.aris3_client_sdk.modules.users_client import UsersClient


class AdminAdapter:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.tenants = TenantsClient(http=http, auth_store=auth_store)
        self.stores = StoresClient(http=http, auth_store=auth_store)
        self.users = UsersClient(http=http, auth_store=auth_store)

    def list_tenants(self) -> list[Tenant]:
        return [Tenant(**item) for item in self.tenants.list()]

    def create_tenant(self, name: str, idempotency_key: str, transaction_id: str) -> dict:
        return self.tenants.create(name=name, idempotency_key=idempotency_key, transaction_id=transaction_id)

    def list_stores(self, tenant_id: str) -> list[Store]:
        return [Store(**item) for item in self.stores.list(tenant_id=tenant_id)]

    def create_store(self, tenant_id: str, name: str, idempotency_key: str, transaction_id: str) -> dict:
        return self.stores.create(
            tenant_id=tenant_id,
            name=name,
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )

    def list_users(self, tenant_id: str) -> list[User]:
        return [User(**item) for item in self.users.list(tenant_id=tenant_id)]

    def create_user(
        self,
        tenant_id: str,
        email: str,
        password: str,
        store_id: str | None,
        idempotency_key: str,
        transaction_id: str,
    ) -> dict:
        return self.users.create(
            tenant_id=tenant_id,
            email=email,
            password=password,
            store_id=store_id,
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )

    def user_action(self, user_id: str, action: str, payload: dict, idempotency_key: str, transaction_id: str) -> dict:
        return self.users.action(
            user_id=user_id,
            action=action,
            payload=payload,
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )
