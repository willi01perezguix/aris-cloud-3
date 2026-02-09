from __future__ import annotations

from dataclasses import dataclass

from ..models_pos_cash import PosCashSessionCurrentResponse
from .base import BaseClient


@dataclass
class PosCashClient(BaseClient):
    def get_current_session(
        self,
        *,
        store_id: str | None = None,
        cashier_user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> PosCashSessionCurrentResponse:
        params = {key: value for key, value in {
            "store_id": store_id,
            "cashier_user_id": cashier_user_id,
            "tenant_id": tenant_id,
        }.items() if value is not None}
        data = self._request("GET", "/aris3/pos/cash/session/current", params=params or None)
        if not isinstance(data, dict):
            raise ValueError("Expected current cash session response to be a JSON object")
        return PosCashSessionCurrentResponse.model_validate(data)
