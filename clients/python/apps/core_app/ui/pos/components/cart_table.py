from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class CartTable:
    lines: list[dict[str, Any]]

    def render(self) -> dict[str, Any]:
        line_total = Decimal("0.00")
        for line in self.lines:
            qty = int(line.get("qty", 0) or 0)
            unit_price = Decimal(str(line.get("unit_price", "0") or "0"))
            line_total += unit_price * qty
        return {
            "count": len(self.lines),
            "line_total": line_total,
            "rows": self.lines,
        }
