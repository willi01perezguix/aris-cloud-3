from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.admin_client import AdminClient
from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider
from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger

from apps.control_center.app.state import OperationRecord, SessionState
from apps.control_center.ui.access.policy_diff_panel import build_policy_change_preview


@dataclass(frozen=True)
class LayeredPolicyView:
    template_allow: list[str]
    tenant_allow: list[str]
    tenant_deny: list[str]
    store_allow: list[str]
    store_deny: list[str]
    user_allow: list[str]
    user_deny: list[str]


class AccessControlService:
    def __init__(
        self,
        access_client: AccessControlClient,
        admin_client: AdminClient,
        state: SessionState,
        *,
        flags: FeatureFlagStore | None = None,
        telemetry: TelemetryLogger | None = None,
    ) -> None:
        self.access_client = access_client
        self.admin_client = admin_client
        self.state = state
        self.flags = flags or FeatureFlagStore(provider=DictFlagProvider(values={}))
        self.telemetry = telemetry or TelemetryLogger(app_name="control_center", enabled=False)

    def effective_permissions_for_user(self, user_id: str, *, store_id: str | None = None) -> dict[str, Any]:
        if store_id:
            data = self.admin_client._request("GET", "/aris3/admin/access-control/effective-permissions", params={"user_id": user_id, "store_id": store_id})
        else:
            data = self.access_client.effective_permissions_for_user(user_id).model_dump(mode="json")
        self.telemetry.emit(
            build_event(
                category="navigation",
                name="cc_screen_view",
                module="control_center",
                action="effective_permissions.view",
                trace_id=data.get("trace_id"),
                success=True,
                context={"has_store_context": bool(store_id)},
            )
        )
        return data

    def build_layered_view(self, effective_permissions: dict[str, Any]) -> LayeredPolicyView:
        trace = effective_permissions.get("sources_trace", {})
        return LayeredPolicyView(
            template_allow=sorted(trace.get("template", {}).get("allow", [])),
            tenant_allow=sorted(trace.get("tenant", {}).get("allow", [])),
            tenant_deny=sorted(trace.get("tenant", {}).get("deny", [])),
            store_allow=sorted(trace.get("store", {}).get("allow", [])),
            store_deny=sorted(trace.get("store", {}).get("deny", [])),
            user_allow=sorted(trace.get("user", {}).get("allow", [])),
            user_deny=sorted(trace.get("user", {}).get("deny", [])),
        )

    def preview_policy_update(self, *, before: dict[str, list[str]], after: dict[str, list[str]]) -> dict[str, list[str]]:
        return build_policy_change_preview(before, after)

    def apply_policy_update(
        self,
        *,
        scope: str,
        scope_id: str,
        role_name: str,
        allow: list[str],
        deny: list[str],
        transaction_id: str,
        idempotency_key: str,
    ) -> OperationRecord:
        route = {
            "tenant": f"/aris3/admin/access-control/tenant-role-policies/{role_name}",
            "store": f"/aris3/admin/access-control/store-role-policies/{scope_id}/{role_name}",
        }[scope]
        self.telemetry.emit(
            build_event(
                category="api_call_result",
                name="cc_policy_edit_attempt",
                module="control_center",
                action=f"policy.update.{scope}",
                success=None,
                context={"scope": scope},
            )
        )
        self.admin_client._request(
            "PUT",
            route,
            json={"allow": allow, "deny": deny, "transaction_id": transaction_id},
            headers={"Idempotency-Key": idempotency_key},
        )
        self.telemetry.emit(
            build_event(
                category="api_call_result",
                name="cc_policy_edit_result",
                module="control_center",
                action=f"policy.update.{scope}",
                success=True,
                context={"scope": scope, "flag_enabled": self.flags.enabled("cc_rbac_editor_v2", default=False)},
            )
        )
        return self._record(
            action=f"access_control.{scope}.policy.update",
            target=f"{scope}:{scope_id}:{role_name}",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )

    def update_user_override(
        self,
        *,
        user_id: str,
        allow: list[str],
        deny: list[str],
        transaction_id: str,
        idempotency_key: str,
    ) -> OperationRecord:
        self.admin_client._request(
            "PATCH",
            f"/aris3/admin/access-control/user-overrides/{user_id}",
            json={"allow": allow, "deny": deny, "transaction_id": transaction_id},
            headers={"Idempotency-Key": idempotency_key},
        )
        return self._record(
            action="access_control.user_override.update",
            target=f"user:{user_id}",
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )

    def _record(self, *, action: str, target: str, idempotency_key: str, transaction_id: str) -> OperationRecord:
        operation = OperationRecord(
            actor=self.state.actor or "unknown",
            target=target,
            action=action,
            at=datetime.now(timezone.utc),
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )
        self.state.add_operation(operation)
        return operation


def deny_wins(permission_rows: list[dict[str, Any]]) -> dict[str, bool]:
    resolved: dict[str, bool] = {}
    for row in permission_rows:
        key = row["key"]
        allowed = bool(row.get("allowed"))
        source = (row.get("source") or "").lower()
        if "deny" in source:
            resolved[key] = False
        elif key not in resolved:
            resolved[key] = allowed
    return resolved


def blocked_admin_grants(actor_permissions: set[str], requested_grants: set[str]) -> set[str]:
    return {grant for grant in requested_grants if grant not in actor_permissions}
