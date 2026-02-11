from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.stock_service import StockMutationResult, StockService, StockServiceError
from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger
from ui.shared.error_presenter import ErrorPresenter
from ui.shared.validators import validate_import_epc_lines
from ui.shared.state_widgets import StateWidget
from ui.shared.view_state import resolve_state
from ui.stock.stock_list_view import StockListView


@dataclass
class ImportEpcView:
    service: StockService
    list_view: StockListView
    telemetry: TelemetryLogger = field(default_factory=lambda: TelemetryLogger(app_name="core_app", enabled=False))
    is_submitting: bool = False
    last_payload: list[dict[str, Any]] = field(default_factory=list)

    def submit(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        self.last_payload = lines
        if not self.list_view.can_import_epc():
            self.telemetry.emit(build_event(category="permission_denied", name="permission_denied", module="stock", action="import_epc"))
            return {"ok": False, "error": "You do not have permission to import EPC stock"}
        validation = validate_import_epc_lines(lines)
        if not validation.ok:
            self.telemetry.emit(
                build_event(
                    category="error",
                    name="validation_failed",
                    module="stock",
                    action="import_epc",
                    success=False,
                    error_code="validation",
                    context={"field_count": len(validation.field_errors)},
                )
            )
            return {
                "ok": False,
                "error": ", ".join(validation.field_errors.keys()) if validation.field_errors else "Validation failed",
                "field_errors": validation.field_errors,
                "summary": validation.summary,
                "values": self.last_payload,
            }
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
            use_v2 = self.list_view.flags.enabled("improved_error_presenter_v2", default=False)
            presented = ErrorPresenter().present(
                message=exc.message,
                details=exc.details,
                trace_id=exc.trace_id,
                action="stock.import_epc",
                allow_retry=False,
            )
            return {
                "ok": False,
                "error": presented.user_message if use_v2 else exc.message,
                "details": presented.details,
                "category": presented.category,
                "trace_id": exc.trace_id,
                "not_applied": True,
                "values": self.last_payload,
            }
        finally:
            self.is_submitting = False

    def render(self) -> dict[str, Any]:
        state = resolve_state(can_view=True, is_loading=self.is_submitting, error=None, has_data=True)
        return {"is_submitting": self.is_submitting, "view_state": StateWidget(state).render()}
