from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.stock_service import StockMutationResult, StockService, StockServiceError
from ui.stock.stock_list_view import StockListView


@dataclass
class MigrateSkuToEpcView:
    service: StockService
    list_view: StockListView
    is_submitting: bool = False

    def expected_effect(self) -> str:
        return "PENDING -1, RFID +1, TOTAL unchanged"

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
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
            return {
                "ok": False,
                "error": exc.message,
                "details": exc.details,
                "trace_id": exc.trace_id,
                "expected_effect": self.expected_effect(),
            }
        finally:
            self.is_submitting = False
