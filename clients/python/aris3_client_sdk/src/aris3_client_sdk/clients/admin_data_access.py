from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import BaseClient


@dataclass
class RetryableMutation:
    """Manual retry handle for mutation calls preserving headers/idempotency."""

    execute_fn: Any

    def retry(self):
        return self.execute_fn()


class AdminDataAccessClient(BaseClient):
    module = "admin"

    def switch_context(self, *, tenant_id: str | None = None, role: str | None = None, session_id: str | None = None) -> int:
        context_key = f"tenant={tenant_id or '-'}|role={role or '-'}|session={session_id or '-'}"
        return self.http.switch_context(context_key)

    def list_tenants(self, *, status: str | None = None):
        params = {"status": status} if status else None
        return self._request(
            "GET",
            "/aris3/admin/tenants",
            params=params,
            module=self.module,
            operation="tenants.list",
        )

    def get_tenant(self, tenant_id: str):
        return self._request(
            "GET",
            f"/aris3/admin/tenants/{tenant_id}",
            module=self.module,
            operation="tenants.get",
        )

    def create_tenant(self, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "POST",
            "/aris3/admin/tenants",
            payload,
            operation="tenants.create",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/tenants"],
        )

    def update_tenant(self, tenant_id: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PATCH",
            f"/aris3/admin/tenants/{tenant_id}",
            payload,
            operation="tenants.update",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/tenants"],
        )

    def list_stores(self, *, tenant_id: str | None = None):
        params = {"tenant_id": tenant_id} if tenant_id else None
        return self._request("GET", "/aris3/admin/stores", params=params, module=self.module, operation="stores.list")

    def get_store(self, store_id: str):
        return self._request("GET", f"/aris3/admin/stores/{store_id}", module=self.module, operation="stores.get")

    def create_store(self, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "POST",
            "/aris3/admin/stores",
            payload,
            operation="stores.create",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/stores"],
        )

    def update_store(self, store_id: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PATCH",
            f"/aris3/admin/stores/{store_id}",
            payload,
            operation="stores.update",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/stores", "/aris3/admin/users"],
        )

    def list_users(self, *, tenant_id: str | None = None, store_id: str | None = None):
        params = {"tenant_id": tenant_id, "store_id": store_id}
        params = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", "/aris3/admin/users", params=params or None, module=self.module, operation="users.list")

    def get_user(self, user_id: str):
        return self._request("GET", f"/aris3/admin/users/{user_id}", module=self.module, operation="users.get")

    def create_user(self, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "POST",
            "/aris3/admin/users",
            payload,
            operation="users.create",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/users"],
        )

    def update_user(self, user_id: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PATCH",
            f"/aris3/admin/users/{user_id}",
            payload,
            operation="users.update",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/users"],
        )

    def delete_tenant(self, tenant_id: str):
        return self._request("DELETE", f"/aris3/admin/tenants/{tenant_id}", module=self.module, operation="tenants.delete")

    def tenant_action(self, tenant_id: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "POST",
            f"/aris3/admin/tenants/{tenant_id}/actions",
            payload,
            operation="tenants.actions",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/tenants"],
        )

    def delete_store(self, store_id: str):
        return self._request("DELETE", f"/aris3/admin/stores/{store_id}", module=self.module, operation="stores.delete")

    def delete_user(self, user_id: str):
        return self._request("DELETE", f"/aris3/admin/users/{user_id}", module=self.module, operation="users.delete")

    def user_action(self, user_id: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "POST",
            f"/aris3/admin/users/{user_id}/actions",
            payload,
            operation="users.actions",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=["/aris3/admin/users"],
        )

    def get_permission_catalog(self):
        return self._request("GET", "/aris3/admin/access-control/permission-catalog", module=self.module, operation="access_control.permissions.catalog")

    def get_role_template(self, role_name: str):
        return self._request("GET", f"/aris3/admin/access-control/role-templates/{role_name}", module=self.module, operation="access_control.role_templates.get")

    def replace_role_template(self, role_name: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PUT",
            f"/aris3/admin/access-control/role-templates/{role_name}",
            payload,
            operation="access_control.role_templates.replace",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=[],
        )

    def get_tenant_role_policy(self, role_name: str):
        return self._request("GET", f"/aris3/admin/access-control/tenant-role-policies/{role_name}", module=self.module, operation="access_control.tenant_role_policies.get")

    def replace_tenant_role_policy(self, role_name: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PUT",
            f"/aris3/admin/access-control/tenant-role-policies/{role_name}",
            payload,
            operation="access_control.tenant_role_policies.replace",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=[],
        )

    def get_store_role_policy(self, store_id: str, role_name: str):
        return self._request("GET", f"/aris3/admin/access-control/store-role-policies/{store_id}/{role_name}", module=self.module, operation="access_control.store_role_policies.get")

    def replace_store_role_policy(self, store_id: str, role_name: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PUT",
            f"/aris3/admin/access-control/store-role-policies/{store_id}/{role_name}",
            payload,
            operation="access_control.store_role_policies.replace",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=[],
        )

    def get_user_overrides(self, user_id: str):
        return self._request("GET", f"/aris3/admin/access-control/user-overrides/{user_id}", module=self.module, operation="access_control.user_overrides.get")

    def patch_user_overrides(self, user_id: str, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PATCH",
            f"/aris3/admin/access-control/user-overrides/{user_id}",
            payload,
            operation="access_control.user_overrides.patch",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=[],
        )

    def get_effective_permissions(self, user_id: str, *, store_id: str | None = None):
        params = {"user_id": user_id}
        if store_id is not None:
            params["store_id"] = store_id
        return self._request("GET", "/aris3/admin/access-control/effective-permissions", params=params, module=self.module, operation="access_control.effective_permissions.get")

    def get_return_policy(self):
        return self._request("GET", "/aris3/admin/settings/return-policy", module=self.module, operation="settings.return_policy.get")

    def patch_return_policy(self, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PATCH",
            "/aris3/admin/settings/return-policy",
            payload,
            operation="settings.return_policy.patch",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=[],
        )

    def get_variant_fields(self):
        return self._request("GET", "/aris3/admin/settings/variant-fields", module=self.module, operation="settings.variant_fields.get")

    def patch_variant_fields(self, payload: dict[str, Any], *, idempotency_key: str, transaction_id: str) -> RetryableMutation:
        return self._mutation_handle(
            "PATCH",
            "/aris3/admin/settings/variant-fields",
            payload,
            operation="settings.variant_fields.patch",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            invalidate_paths=[],
        )

    def _mutation_handle(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        *,
        operation: str,
        idempotency_key: str,
        transaction_id: str,
        invalidate_paths: list[str],
    ) -> RetryableMutation:
        headers = {"Idempotency-Key": idempotency_key, "transaction_id": transaction_id}

        def _run():
            return self._request(
                method,
                path,
                json_body=payload,
                headers=headers,
                module=self.module,
                operation=operation,
                invalidate_paths=invalidate_paths,
            )

        return RetryableMutation(execute_fn=_run)
