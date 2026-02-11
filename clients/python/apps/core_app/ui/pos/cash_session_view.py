from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.permissions_service import PermissionGate
from services.pos_cash_service import PosCashService, PosCashServiceError
from ui.pos.components.cash_status_chip import CashStatusChip

POS_CASH_READ: tuple[str, ...] = ("pos.cash.view", "POS_CASH_VIEW")
POS_CASH_WRITE: tuple[str, ...] = ("pos.cash.write", "POS_CASH_WRITE")


@dataclass
class CashSessionView:
    service: PosCashService
    gate: PermissionGate
    session_payload: dict[str, Any] | None = None
    error_message: str | None = None
    trace_id: str | None = None
    is_submitting: bool = False

    def can_view(self) -> bool:
        return self.gate.allows_any(*POS_CASH_READ)

    def can_mutate(self) -> bool:
        return self.gate.allows_any(*POS_CASH_WRITE)

    def load_current(self, *, store_id: str | None = None, tenant_id: str | None = None) -> bool:
        if not self.can_view():
            self.error_message = "You do not have permission to view POS cash sessions"
            self.session_payload = None
            return False
        try:
            response = self.service.current_session(store_id=store_id, tenant_id=tenant_id)
            self.session_payload = response.session.model_dump(mode="json", exclude_none=True) if response.session else None
            self.error_message = None
            return True
        except PosCashServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            self.session_payload = None
            return False

    def open(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._mutate("OPEN", payload)

    def cash_in(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._mutate("CASH_IN", payload)

    def cash_out(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._mutate("CASH_OUT", payload)

    def close(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._mutate("CLOSE", payload)

    def can_action(self, action: str) -> bool:
        status = (self.session_payload or {}).get("status")
        if action == "OPEN":
            return status != "OPEN"
        if action in {"CASH_IN", "CASH_OUT", "CLOSE"}:
            return status == "OPEN"
        return False

    def _mutate(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.can_mutate():
            return {"ok": False, "error": "You do not have permission to modify POS cash sessions"}
        if not self.can_action(action):
            return {"ok": False, "error": f"Action {action} is not allowed in the current cash state"}
        if self.is_submitting:
            return {"ok": False, "error": "Cash action already in progress"}
        self.is_submitting = True
        try:
            if action == "OPEN":
                outcome = self.service.open_session(payload)
            elif action == "CASH_IN":
                outcome = self.service.cash_in(payload)
            elif action == "CASH_OUT":
                outcome = self.service.cash_out(payload)
            else:
                outcome = self.service.close_session(payload)
            self.session_payload = outcome.response.model_dump(mode="json", exclude_none=True)
            return {
                "ok": True,
                "session": self.session_payload,
                "transaction_id": outcome.meta.transaction_id,
                "idempotency_key": outcome.meta.idempotency_key,
            }
        except PosCashServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            return {"ok": False, "error": exc.message, "trace_id": exc.trace_id, "details": exc.details}
        finally:
            self.is_submitting = False

    def render(self) -> dict[str, Any]:
        return {
            "can_view": self.can_view(),
            "can_mutate": self.can_mutate(),
            "status_chip": CashStatusChip(self.session_payload).render(),
            "action_enabled": {
                "open": self.can_action("OPEN"),
                "cash_in": self.can_action("CASH_IN"),
                "cash_out": self.can_action("CASH_OUT"),
                "close": self.can_action("CLOSE"),
            },
            "session": self.session_payload,
            "error": self.error_message,
            "trace_id": self.trace_id,
        }
