from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aris3_client_sdk.clients.admin_client import AdminClient
from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider
from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger

from apps.control_center.app.state import OperationRecord, SessionState


@dataclass
class UserMutationResult:
    user: dict[str, Any]
    trace_id: str | None
    operation: OperationRecord
    refresh_required: bool = True


class AdminUsersService:
    def __init__(
        self,
        client: AdminClient,
        state: SessionState,
        *,
        flags: FeatureFlagStore | None = None,
        telemetry: TelemetryLogger | None = None,
    ) -> None:
        self.client = client
        self.state = state
        self.flags = flags or FeatureFlagStore(provider=DictFlagProvider(values={}))
        self.telemetry = telemetry or TelemetryLogger(app_name="control_center", enabled=False)

    def list_users(self, *, query: str = "") -> tuple[list[dict[str, Any]], str | None]:
        payload = self.client._request("GET", "/aris3/admin/users")
        users = payload.get("users", [])
        if query:
            query_lower = query.lower()
            users = [u for u in users if query_lower in u.get("username", "").lower() or query_lower in u.get("email", "").lower()]
        return users, payload.get("trace_id")

    def create_user(self, payload: dict[str, Any], *, idempotency_key: str) -> UserMutationResult:
        response = self.client._request("POST", "/aris3/admin/users", json=payload, headers={"Idempotency-Key": idempotency_key})
        user = response["user"]
        op = self._record("admin.user.create", target=user["id"], trace_id=response.get("trace_id"), idempotency_key=idempotency_key)
        return UserMutationResult(user=user, trace_id=response.get("trace_id"), operation=op)

    def update_user(self, user_id: str, payload: dict[str, Any]) -> UserMutationResult:
        response = self.client._request("PATCH", f"/aris3/admin/users/{user_id}", json=payload)
        user = response["user"]
        op = self._record("admin.user.update", target=user_id, trace_id=response.get("trace_id"))
        return UserMutationResult(user=user, trace_id=response.get("trace_id"), operation=op)

    def user_action(self, user_id: str, payload: dict[str, Any], *, idempotency_key: str) -> UserMutationResult:
        self.telemetry.emit(
            build_event(
                category="api_call_result",
                name="cc_user_action_attempt",
                module="control_center",
                action=str(payload.get("action") or "unknown"),
                success=None,
                context={"flag_enabled": self.flags.enabled("cc_safe_actions_v1", default=False)},
            )
        )
        response = self.client._request(
            "POST",
            f"/aris3/admin/users/{user_id}/actions",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        user = response["user"]
        op = self._record(
            f"admin.user.action.{payload.get('action')}",
            target=user_id,
            trace_id=response.get("trace_id"),
            idempotency_key=idempotency_key,
            transaction_id=payload.get("transaction_id"),
        )
        self.telemetry.emit(
            build_event(
                category="api_call_result",
                name="cc_user_action_result",
                module="control_center",
                action=str(payload.get("action") or "unknown"),
                success=True,
                trace_id=response.get("trace_id"),
                context={"has_reason": bool(payload.get("reason"))},
            )
        )
        return UserMutationResult(user=user, trace_id=response.get("trace_id"), operation=op, refresh_required=True)

    def _record(self, action: str, *, target: str, trace_id: str | None, idempotency_key: str | None = None, transaction_id: str | None = None) -> OperationRecord:
        operation = OperationRecord(
            actor=self.state.actor or "unknown",
            target=target,
            action=action,
            at=datetime.now(timezone.utc),
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )
        self.state.add_operation(operation)
        return operation
