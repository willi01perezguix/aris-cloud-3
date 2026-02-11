from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.stock_service import StockMutationResult, StockService, StockServiceError
from ui.shared.error_presenter import ErrorPresenter
from ui.shared.state_widgets import StateWidget
from ui.shared.view_state import resolve_state
from ui.stock.stock_list_view import StockListView


@dataclass
class MigrateSkuToEpcView:
    service: StockService
    list_view: StockListView
    is_submitting: bool = False
    last_payload: dict[str, Any] = field(default_factory=dict)

    def expected_effect(self) -> str:
        return "PENDING -1, RFID +1, TOTAL unchanged"

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_payload = payload
        if not self.list_view.can_migrate():
            return {"ok": False, "error": "You do not have permission to migrate SKU to EPC"}
        if self.is_submitting:
            return {"ok": False, "error": "Migration already in progress"}
        self.is_submitting = True
        try:
            outcome: StockMutationResult = self.service.migrate_sku_to_epc(payload)
            self.list_view.refresh()
            return {
                "ok": True,
                "migrated": getattr(outcome.response, "migrated", None),
                "line_results": [r.model_dump(mode="json", exclude_none=True) for r in (outcome.response.line_results or [])],
                "trace_id": outcome.response.trace_id,
                "transaction_id": outcome.meta.transaction_id,
                "idempotency_key": outcome.meta.idempotency_key,
                "expected_effect": self.expected_effect(),
            }
        except StockServiceError as exc:
            use_v2 = self.list_view.flags.enabled("improved_error_presenter_v2", default=False)
            presented = ErrorPresenter().present(
                message=exc.message,
                details=exc.details,
                trace_id=exc.trace_id,
                action="stock.migrate_sku_to_epc",
                allow_retry=False,
            )
            return {
                "ok": False,
                "error": presented.user_message if use_v2 else exc.message,
                "details": presented.details,
                "category": presented.category,
                "trace_id": exc.trace_id,
                "expected_effect": self.expected_effect(),
                "not_applied": True,
                "values": self.last_payload,
            }
        finally:
            self.is_submitting = False

    def render(self) -> dict[str, Any]:
        state = resolve_state(can_view=True, is_loading=self.is_submitting, error=None, has_data=True)
        return {"is_submitting": self.is_submitting, "view_state": StateWidget(state).render()}
