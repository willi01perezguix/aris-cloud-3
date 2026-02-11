from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aris3_client_sdk.models_stock import StockTotals


@dataclass
class StockTotalsBar:
    totals: StockTotals

    def render(self) -> dict[str, Any]:
        payload = self.totals.model_dump(mode="json", exclude_none=True)
        return {
            "rfid": self.totals.total_rfid,
            "pending": self.totals.total_pending,
            "total": self.totals.total_units,
            "raw_totals": payload,
        }
