from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models_stock import StockQuery, StockTableResponse
from .base import BaseClient


@dataclass
class StockClient(BaseClient):
    def get_stock(self, filters: StockQuery) -> StockTableResponse:
        params = build_stock_params(filters)
        payload = self._request("GET", "/aris3/stock", params=params)
        if not isinstance(payload, dict):
            raise ValueError("Expected stock query response to be a JSON object")
        return StockTableResponse.model_validate(payload)


def build_stock_params(filters: StockQuery) -> dict[str, Any]:
    return filters.model_dump(by_alias=True, exclude_none=True, mode="json")
