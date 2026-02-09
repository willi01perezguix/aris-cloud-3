from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class PosCashSessionActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    store_id: str
    action: Literal["OPEN", "CASH_IN", "CASH_OUT", "CLOSE"]
    opening_amount: Decimal | None = None
    amount: Decimal | None = None
    counted_cash: Decimal | None = None
    business_date: date | None = None
    timezone: str | None = None
    reason: str | None = None


class PosCashSessionSummary(BaseModel):
    id: str
    tenant_id: str
    store_id: str
    cashier_user_id: str
    status: str
    business_date: date
    timezone: str
    opening_amount: Decimal
    expected_cash: Decimal
    counted_cash: Decimal | None
    difference: Decimal | None
    opened_at: datetime
    closed_at: datetime | None
    created_at: datetime


class PosCashSessionCurrentResponse(BaseModel):
    session: PosCashSessionSummary | None


class PosCashMovementResponse(BaseModel):
    id: str
    tenant_id: str
    store_id: str
    cashier_user_id: str
    cash_session_id: str
    sale_id: str | None
    business_date: date
    timezone: str
    movement_type: str
    amount: Decimal
    expected_balance_before: Decimal | None
    expected_balance_after: Decimal | None
    transaction_id: str | None
    reason: str | None
    created_at: datetime


class PosCashMovementListResponse(BaseModel):
    rows: list[PosCashMovementResponse]
    total: int


class PosCashDayCloseActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    store_id: str
    action: Literal["CLOSE_DAY"] = "CLOSE_DAY"
    business_date: date
    timezone: str
    force_if_open_sessions: bool | None = None
    reason: str | None = None


class PosCashDayCloseResponse(BaseModel):
    id: str
    tenant_id: str
    store_id: str
    business_date: date
    timezone: str
    status: str
    force_close: bool
    reason: str | None
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime
