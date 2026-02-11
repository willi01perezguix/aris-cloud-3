from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.permissions_service import PermissionGate
from services.stock_service import StockService, StockServiceError
from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider
from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger
from ui.shared.notification_center import NotificationCenter
from ui.shared.retry_panel import RetryPanel
from ui.shared.state_widgets import StateWidget
from ui.shared.view_state import resolve_state
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
    flags: FeatureFlagStore = field(default_factory=lambda: FeatureFlagStore(provider=DictFlagProvider(values={})))
    telemetry: TelemetryLogger = field(default_factory=lambda: TelemetryLogger(app_name="core_app", enabled=False))
    last_filters: dict[str, Any] = field(default_factory=dict)
    is_loading: bool = False
    error_message: str | None = None
    trace_id: str | None = None
    rows_payload: dict[str, Any] | None = None
    totals_payload: dict[str, Any] | None = None
    meta_payload: dict[str, Any] | None = None
    last_snapshot: dict[str, Any] | None = None
    notifications: NotificationCenter = field(default_factory=NotificationCenter)

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
            self.last_snapshot = {
                "meta": self.meta_payload,
                "table": self.rows_payload,
                "totals": self.totals_payload,
                "trace_id": self.trace_id,
            }
            self.telemetry.emit(
                build_event(
                    category="navigation",
                    name="screen_view",
                    module="stock",
                    action="stock_list.load",
                    success=True,
                    trace_id=self.trace_id,
                )
            )
            return True
        except StockServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            keep_snapshot = self.flags.enabled("optimistic_ui_reads_v1", default=False) and self.last_snapshot is not None
            if keep_snapshot and self.last_snapshot is not None:
                self.meta_payload = self.last_snapshot.get("meta")
                self.rows_payload = self.last_snapshot.get("table")
                self.totals_payload = self.last_snapshot.get("totals")
                self.notifications.push(
                    level="warning",
                    title="Read retry available",
                    message="Showing last successful data snapshot.",
                    details={"trace_id": self.trace_id},
                )
            else:
                self.rows_payload = None
                self.totals_payload = None
                self.meta_payload = None
            self.telemetry.emit(
                build_event(
                    category="api_call_result",
                    name="api_call_result",
                    module="stock",
                    action="stock_list.load",
                    success=False,
                    trace_id=self.trace_id,
                    error_code="read_failed",
                )
            )
            return False
        finally:
            self.is_loading = False

    def refresh(self) -> bool:
        return self.load(self.last_filters)

    def render(self) -> dict[str, Any]:
        state = resolve_state(
            can_view=self.can_view(),
            is_loading=self.is_loading,
            error=self.error_message,
            has_data=bool(self.rows_payload),
            trace_id=self.trace_id,
        )
        retry = RetryPanel(operation="stock_list.load", is_mutation=False, idempotent=True, has_transient_error=bool(self.error_message))
        retry_payload = retry.render() if self.flags.enabled("advanced_retry_panel_v1", default=False) else {"operation": "stock_list.load", "enabled": False, "warning": "Retry panel gated by flag."}
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
            "view_state": StateWidget(state).render(),
            "notifications": self.notifications.render(),
            "retry": retry_payload,
            "filters": self.last_filters,
        }
