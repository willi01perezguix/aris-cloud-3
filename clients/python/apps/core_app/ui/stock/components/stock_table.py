from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aris3_client_sdk.models_stock import StockRow


@dataclass
class StockTable:
    rows: list[StockRow]

    def columns(self) -> list[str]:
        columns: list[str] = []
        for row in self.rows:
            for key in row.model_dump(exclude_none=True).keys():
                if key not in columns:
                    columns.append(key)
        return columns

    def render(self) -> dict[str, Any]:
        return {
            "columns": self.columns(),
            "rows": [row.model_dump(mode="json", exclude_none=True) for row in self.rows],
            "count": len(self.rows),
        }
