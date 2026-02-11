from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.permissions_service import PermissionGate
from services.pos_cash_service import PosCashService
from services.pos_sales_service import PosSalesService
from ui.pos.cash_movements_view import CashMovementsView
from ui.pos.cash_session_view import CashSessionView
from ui.pos.sales_list_view import SalesListView


@dataclass
class PosShellView:
    sales_service: PosSalesService
    cash_service: PosCashService
    gate: PermissionGate

    def render(self) -> dict[str, Any]:
        sales_view = SalesListView(self.sales_service, self.gate)
        cash_session_view = CashSessionView(self.cash_service, self.gate)
        cash_movements_view = CashMovementsView(self.cash_service, self.gate)
        return {
            "can_view_pos": sales_view.can_view() or cash_session_view.can_view(),
            "sales": sales_view.render(),
            "cash_session": cash_session_view.render(),
            "cash_movements": cash_movements_view.render(),
        }
