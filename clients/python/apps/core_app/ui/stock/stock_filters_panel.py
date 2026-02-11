from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StockFiltersPanel:
    q: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    sku: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    page: int = 1
    page_size: int = 50
    sort_by: str | None = None
    sort_dir: str | None = None

    def as_query(self) -> dict[str, object]:
        values = {
            "q": self.q,
            "description": self.description,
            "var1_value": self.var1_value,
            "var2_value": self.var2_value,
            "sku": self.sku,
            "epc": self.epc,
            "location_code": self.location_code,
            "pool": self.pool,
            "page": self.page,
            "page_size": self.page_size,
            "sort_by": self.sort_by,
            "sort_order": self.sort_dir,
        }
        return {key: value for key, value in values.items() if value not in (None, "")}
