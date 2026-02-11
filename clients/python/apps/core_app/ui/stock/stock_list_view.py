from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.permissions_service import PermissionGate
from services.stock_service import StockService, StockServiceError
from ui.stock.components.stock_table import StockTable
from ui.stock.components.stock_totals_bar import StockTotalsBar

STOCK_READ_PERMISSIONS: tuple[str, ...] = ("stock.view", "STORE_VIEW")
STOCK_IMPORT_EPC_PERMISSIONS: tuple[str, ...] = ("stock.import_epc", "stock.write", "STORE_WRITE")
STOCK_IMPORT_SKU_PERMISSIONS: tuple[str, ...] = ("stock.import_sku", "stock.write", "STORE_WRITE")
STOCK_MIGRATE_PERMISSIONS: tuple[str, ...] = ("stock.migrate_sku_to_epc", "stock.write", "STORE_WRITE")


@dataclass
class StockListView:
    service: StockService
    gate: PermissionGate
    last_filters: dict[str, Any] = field(default_factory=dict)
    is_loading: bool = False
    error_message: str | None = None
    trace_id: str | None = None
    rows_payload: dict[str, Any] | None = None
    totals_payload: dict[str, Any] | None = None
    meta_payload: dict[str, Any] | None = None

    def can_view(self) -> bool:
        return self.gate.allows_any(*STOCK_READ_PERMISSIONS)

    def can_import_epc(self) -> bool:
        return self.gate.allows_any(*STOCK_IMPORT_EPC_PERMISSIONS)

    def can_import_sku(self) -> bool:
        return self.gate.allows_any(*STOCK_IMPORT_SKU_PERMISSIONS)

    def can_migrate(self) -> bool:
        return self.gate.allows_any(*STOCK_MIGRATE_PERMISSIONS)

    def load(self, filters: dict[str, Any]) -> bool:
        self.last_filters = filters
        if not self.can_view():
            self.error_message = "You do not have permission to view stock"
            self.rows_payload = None
            self.totals_payload = None
            self.meta_payload = None
            return False
        self.is_loading = True
        self.error_message = None
        try:
            response = self.service.query_stock(filters)
            self.meta_payload = response.meta.model_dump(mode="json", exclude_none=True)
            self.rows_payload = StockTable(response.rows).render()
            self.totals_payload = StockTotalsBar(response.totals).render()
            self.trace_id = getattr(response, "trace_id", None)
            return True
        except StockServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            self.rows_payload = None
            self.totals_payload = None
            self.meta_payload = None
            return False
        finally:
            self.is_loading = False

    def refresh(self) -> bool:
        return self.load(self.last_filters)

    def render(self) -> dict[str, Any]:
        return {
            "can_view": self.can_view(),
            "actions": {
                "import_epc": self.can_import_epc(),
                "import_sku": self.can_import_sku(),
                "migrate_sku_to_epc": self.can_migrate(),
            },
            "loading": self.is_loading,
            "error": self.error_message,
            "meta": self.meta_payload,
            "table": self.rows_payload,
            "totals": self.totals_payload,
            "trace_id": self.trace_id,
            "empty": bool(self.rows_payload and self.rows_payload.get("count") == 0),
        }
