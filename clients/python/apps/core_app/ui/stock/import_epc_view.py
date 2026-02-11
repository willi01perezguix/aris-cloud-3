from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.stock_service import StockMutationResult, StockService, StockServiceError
from ui.stock.stock_list_view import StockListView


@dataclass
class ImportEpcView:
    service: StockService
    list_view: StockListView
    is_submitting: bool = False

    def submit(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.list_view.can_import_epc():
            return {"ok": False, "error": "You do not have permission to import EPC stock"}
        if self.is_submitting:
            return {"ok": False, "error": "Import already in progress"}
        self.is_submitting = True
        try:
            outcome: StockMutationResult = self.service.import_epc(lines)
            self.list_view.refresh()
            return {
                "ok": True,
                "processed": outcome.response.processed,
                "line_results": [r.model_dump(mode="json", exclude_none=True) for r in (outcome.response.line_results or [])],
                "trace_id": outcome.response.trace_id,
                "transaction_id": outcome.meta.transaction_id,
                "idempotency_key": outcome.meta.idempotency_key,
            }
        except StockServiceError as exc:
            return {
                "ok": False,
                "error": exc.message,
                "details": exc.details,
                "trace_id": exc.trace_id,
            }
        finally:
            self.is_submitting = False
