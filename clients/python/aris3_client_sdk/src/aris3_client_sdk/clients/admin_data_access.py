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
