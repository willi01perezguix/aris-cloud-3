from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PosCashSessionSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    tenant_id: str | None = None
    store_id: str | None = None
    cashier_user_id: str | None = None
    status: str | None = None
    business_date: date | None = None
    timezone: str | None = None
    opening_amount: float | None = None
    expected_cash: float | None = None
    counted_cash: float | None = None
    difference: float | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime | None = None


class PosCashSessionCurrentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    session: PosCashSessionSummary | None = None
