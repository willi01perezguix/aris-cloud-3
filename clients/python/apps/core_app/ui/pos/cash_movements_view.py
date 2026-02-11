from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.permissions_service import PermissionGate
from services.pos_cash_service import PosCashService, PosCashServiceError
from ui.shared.state_widgets import StateWidget
from ui.shared.view_state import resolve_state

POS_CASH_READ: tuple[str, ...] = ("pos.cash.view", "POS_CASH_VIEW")


@dataclass
class CashMovementsView:
    service: PosCashService
    gate: PermissionGate
    rows: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    error_message: str | None = None
    trace_id: str | None = None
    is_loading: bool = False

    def can_view(self) -> bool:
        return self.gate.allows_any(*POS_CASH_READ)

    def load(self, **filters: Any) -> bool:
        if not self.can_view():
            self.error_message = "You do not have permission to view POS cash movements"
            self.rows = []
            self.total = 0
            return False
        self.is_loading = True
        try:
            response = self.service.movements(**filters)
            self.rows = [row.model_dump(mode="json", exclude_none=True) for row in response.rows]
            self.total = response.total
            self.error_message = None
            return True
        except PosCashServiceError as exc:
            self.error_message = exc.message
            self.trace_id = exc.trace_id
            self.rows = []
            self.total = 0
            return False
        finally:
            self.is_loading = False

    def render(self) -> dict[str, Any]:
        state = resolve_state(can_view=self.can_view(), is_loading=self.is_loading, error=self.error_message, has_data=bool(self.rows), trace_id=self.trace_id)
        return {
            "can_view": self.can_view(),
            "rows": self.rows,
            "total": self.total,
            "error": self.error_message,
            "trace_id": self.trace_id,
            "view_state": StateWidget(state).render(),
        }
