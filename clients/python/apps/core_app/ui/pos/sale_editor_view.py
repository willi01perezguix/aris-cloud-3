from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from services.permissions_service import PermissionGate
from services.pos_cash_service import PosCashService
from services.pos_sales_service import PosSalesService, PosSalesServiceError
from ui.pos.components.cart_table import CartTable
from ui.pos.components.payment_summary_bar import PaymentSummaryBar
from ui.pos.payment_dialog import PaymentDialog
from ui.shared.error_presenter import ErrorPresenter
from ui.shared.validators import validate_payments

POS_SALES_WRITE: tuple[str, ...] = ("pos.sales.write", "POS_SALE_WRITE")
POS_SALES_CHECKOUT: tuple[str, ...] = ("pos.sales.checkout", "pos.sales.action", "POS_SALE_WRITE")
POS_SALES_CANCEL: tuple[str, ...] = ("pos.sales.cancel", "pos.sales.action", "POS_SALE_WRITE")


@dataclass
class SaleEditorView:
    service: PosSalesService
    cash_service: PosCashService
    gate: PermissionGate
    sale_id: str | None = None
    lines: list[dict[str, Any]] = field(default_factory=list)
    payments: list[dict[str, Any]] = field(default_factory=list)
    total_due: Decimal = Decimal("0.00")
    error_message: str | None = None
    trace_id: str | None = None
    is_submitting: bool = False

    def can_write(self) -> bool:
        return self.gate.allows_any(*POS_SALES_WRITE)

    def can_checkout(self) -> bool:
        return self.gate.allows_any(*POS_SALES_CHECKOUT)

    def can_cancel(self) -> bool:
        return self.gate.allows_any(*POS_SALES_CANCEL)

    def create_draft(self, *, store_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        if not self.can_write():
            return {"ok": False, "error": "You do not have permission to create sale drafts"}
        if self.is_submitting:
            return {"ok": False, "error": "Sale mutation already in progress"}
        self.is_submitting = True
        try:
            outcome = self.service.create_draft(store_id=store_id, tenant_id=tenant_id, lines=self.lines)
            self._hydrate(outcome.response)
            return {
                "ok": True,
                "sale_id": self.sale_id,
                "transaction_id": outcome.meta.transaction_id,
                "idempotency_key": outcome.meta.idempotency_key,
            }
        except PosSalesServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            return {"ok": False, "error": exc.message, "trace_id": exc.trace_id, "details": exc.details, "not_applied": True}
        finally:
            self.is_submitting = False

    def load(self, sale_id: str) -> bool:
        try:
            response = self.service.get_sale(sale_id)
            self._hydrate(response)
            return True
        except PosSalesServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            return False

    def add_line(self, line: dict[str, Any]) -> dict[str, Any]:
        qty = int(line.get("qty", 0) or 0)
        if qty <= 0:
            return {"ok": False, "error": "qty must be greater than 0"}
        self.lines.append(line)
        return {"ok": True, "cart": CartTable(self.lines).render()}

    def edit_line(self, index: int, updates: dict[str, Any]) -> dict[str, Any]:
        if index < 0 or index >= len(self.lines):
            return {"ok": False, "error": "line index is out of range"}
        candidate = {**self.lines[index], **updates}
        qty = int(candidate.get("qty", 0) or 0)
        if qty <= 0:
            return {"ok": False, "error": "qty must be greater than 0"}
        self.lines[index] = candidate
        return {"ok": True, "cart": CartTable(self.lines).render()}

    def remove_line(self, index: int) -> dict[str, Any]:
        if index < 0 or index >= len(self.lines):
            return {"ok": False, "error": "line index is out of range"}
        self.lines.pop(index)
        return {"ok": True, "cart": CartTable(self.lines).render()}

    def save_lines(self, tenant_id: str | None = None) -> dict[str, Any]:
        if not self.can_write():
            return {"ok": False, "error": "You do not have permission to update sale drafts"}
        if self.sale_id is None:
            return {"ok": False, "error": "No draft loaded"}
        if self.is_submitting:
            return {"ok": False, "error": "Sale mutation already in progress"}
        self.is_submitting = True
        try:
            outcome = self.service.update_draft(sale_id=self.sale_id, tenant_id=tenant_id, lines=self.lines)
            self._hydrate(outcome.response)
            return {
                "ok": True,
                "sale_id": self.sale_id,
                "transaction_id": outcome.meta.transaction_id,
                "idempotency_key": outcome.meta.idempotency_key,
            }
        except PosSalesServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            return {"ok": False, "error": exc.message, "trace_id": exc.trace_id, "details": exc.details, "not_applied": True}
        finally:
            self.is_submitting = False

    def checkout(self, tenant_id: str | None = None) -> dict[str, Any]:
        if not self.can_checkout():
            return {"ok": False, "error": "You do not have permission to checkout POS sales"}
        if self.sale_id is None:
            return {"ok": False, "error": "No draft loaded"}
        if self.is_submitting:
            return {"ok": False, "error": "Sale mutation already in progress"}
        validation = validate_payments(self.payments, self.total_due)
        if not validation.ok:
            return {
                "ok": False,
                "error": "Invalid payment payload",
                "issues": validation.summary,
                "field_errors": validation.field_errors,
                "summary": self.payment_summary(),
                "values": self.payments,
            }
        dialog = PaymentDialog(total_due=self.total_due, payments=self.payments)
        if not dialog.validate():
            return {"ok": False, "error": "Invalid payment payload", "issues": dialog.issues, "summary": dialog.render()}
        if any((payment.get("method") or "").upper() == "CASH" for payment in self.payments):
            current = self.cash_service.current_session()
            status = current.session.status if current.session else None
            if status != "OPEN":
                return {"ok": False, "error": "CASH checkout requires an OPEN cash session"}
        self.is_submitting = True
        try:
            outcome = self.service.checkout(
                self.sale_id,
                tenant_id=tenant_id,
                payments=self.payments,
                total_due=self.total_due,
            )
            self._hydrate(outcome.response)
            return {
                "ok": True,
                "sale_id": self.sale_id,
                "summary": self.payment_summary(),
                "transaction_id": outcome.meta.transaction_id,
                "idempotency_key": outcome.meta.idempotency_key,
            }
        except PosSalesServiceError as exc:
            presented = ErrorPresenter().present(
                message=exc.message,
                details=exc.details,
                trace_id=exc.trace_id,
                action="pos.checkout",
                allow_retry=False,
            )
            self.error_message = presented.user_message
            self.trace_id = exc.trace_id
            return {
                "ok": False,
                "error": presented.user_message,
                "trace_id": exc.trace_id,
                "details": presented.details,
                "category": presented.category,
                "not_applied": True,
            }
        finally:
            self.is_submitting = False

    def cancel(self, *, confirmed: bool, tenant_id: str | None = None) -> dict[str, Any]:
        if not confirmed:
            return {"ok": False, "error": "Cancel confirmation is required"}
        if not self.can_cancel():
            return {"ok": False, "error": "You do not have permission to cancel POS sales"}
        if self.sale_id is None:
            return {"ok": False, "error": "No draft loaded"}
        if self.is_submitting:
            return {"ok": False, "error": "Sale mutation already in progress"}
        self.is_submitting = True
        try:
            outcome = self.service.cancel(self.sale_id, tenant_id=tenant_id)
            self._hydrate(outcome.response)
            return {
                "ok": True,
                "sale_id": self.sale_id,
                "transaction_id": outcome.meta.transaction_id,
                "idempotency_key": outcome.meta.idempotency_key,
            }
        except PosSalesServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            return {"ok": False, "error": exc.message, "trace_id": exc.trace_id, "details": exc.details, "not_applied": True}
        finally:
            self.is_submitting = False

    def payment_summary(self) -> dict[str, Any]:
        totals = self.service.payment_totals(self.total_due, self.payments)
        return PaymentSummaryBar(**totals).render()

    def render(self) -> dict[str, Any]:
        return {
            "sale_id": self.sale_id,
            "cart": CartTable(self.lines).render(),
            "payment_summary": self.payment_summary(),
            "error": self.error_message,
            "trace_id": self.trace_id,
            "actions": {
                "can_write": self.can_write(),
                "can_checkout": self.can_checkout(),
                "can_cancel": self.can_cancel(),
            },
            "guards": {
                "disable_while_submitting": self.is_submitting,
                "double_submit_protection": True,
                "cancel_requires_confirmation": True,
                "keyboard_shortcuts": ["Ctrl+S", "Ctrl+Enter", "Esc"],
            },
        }

    def _hydrate(self, response: Any) -> None:
        payload = response.model_dump(mode="json", exclude_none=True)
        self.sale_id = payload.get("header", {}).get("id", self.sale_id)
        self.total_due = Decimal(str(payload.get("header", {}).get("total_due", self.total_due)))
        self.lines = [
            {
                "line_type": line.get("line_type"),
                "qty": line.get("qty"),
                "unit_price": line.get("unit_price"),
                "snapshot": line.get("snapshot"),
            }
            for line in payload.get("lines", [])
        ]
        self.error_message = None
