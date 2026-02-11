from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.permissions_service import PermissionGate
from services.pos_sales_service import PosSalesService, PosSalesServiceError

POS_SALES_READ: tuple[str, ...] = ("pos.sales.view", "POS_SALE_VIEW")
POS_SALES_CHECKOUT: tuple[str, ...] = ("pos.sales.checkout", "pos.sales.action", "POS_SALE_WRITE")
POS_SALES_CANCEL: tuple[str, ...] = ("pos.sales.cancel", "pos.sales.action", "POS_SALE_WRITE")


@dataclass
class SalesListView:
    service: PosSalesService
    gate: PermissionGate
    sales: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None
    trace_id: str | None = None

    def can_view(self) -> bool:
        return self.gate.allows_any(*POS_SALES_READ)

    def can_checkout(self) -> bool:
        return self.gate.allows_any(*POS_SALES_CHECKOUT)

    def can_cancel(self) -> bool:
        return self.gate.allows_any(*POS_SALES_CANCEL)

    def load(self, filters: dict[str, Any] | None = None) -> bool:
        if not self.can_view():
            self.error_message = "You do not have permission to view POS sales"
            self.sales = []
            return False
        try:
            response = self.service.list_sales(filters)
            self.sales = [row.model_dump(mode="json", exclude_none=True) for row in response.rows]
            self.error_message = None
            return True
        except PosSalesServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            self.sales = []
            return False

    def render(self) -> dict[str, Any]:
        return {
            "can_view": self.can_view(),
            "actions": {"checkout": self.can_checkout(), "cancel": self.can_cancel()},
            "sales": self.sales,
            "error": self.error_message,
            "trace_id": self.trace_id,
        }
