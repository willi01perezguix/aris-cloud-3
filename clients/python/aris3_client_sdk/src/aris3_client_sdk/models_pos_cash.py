from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

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


class PosCashSessionActionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    store_id: str
    action: Literal["OPEN", "CASH_IN", "CASH_OUT", "CLOSE"]
    opening_amount: Decimal | None = None
    amount: Decimal | None = None
    counted_cash: Decimal | None = None
    business_date: date | None = None
    timezone: str | None = None
    reason: str | None = None


class PosCashMovementResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    tenant_id: str | None = None
    store_id: str | None = None
    cashier_user_id: str | None = None
    actor_user_id: str | None = None
    cash_session_id: str | None = None
    sale_id: str | None = None
    business_date: date | None = None
    timezone: str | None = None
    movement_type: str | None = None
    amount: Decimal | None = None
    expected_balance_before: Decimal | None = None
    expected_balance_after: Decimal | None = None
    transaction_id: str | None = None
    reason: str | None = None
    trace_id: str | None = None
    occurred_at: datetime | None = None
    created_at: datetime | None = None


class PosCashMovementListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: list[PosCashMovementResponse]
    total: int


class PosCashDayCloseActionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    store_id: str
    action: Literal["CLOSE_DAY"] = "CLOSE_DAY"
    business_date: date
    timezone: str
    force_if_open_sessions: bool | None = None
    reason: str | None = None
    counted_cash: Decimal | None = None


class PosCashDayCloseResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    tenant_id: str | None = None
    store_id: str | None = None
    business_date: date | None = None
    timezone: str | None = None
    status: str | None = None
    force_close: bool | None = None
    reason: str | None = None
    expected_cash: Decimal | None = None
    counted_cash: Decimal | None = None
    difference_amount: Decimal | None = None
    difference_type: str | None = None
    net_cash_sales: Decimal | None = None
    cash_refunds: Decimal | None = None
    net_cash_movement: Decimal | None = None
    day_close_difference: Decimal | None = None
    closed_by_user_id: str | None = None
    closed_at: datetime | None = None
    created_at: datetime | None = None


class PosCashDayCloseSummaryListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: list[PosCashDayCloseResponse]
    total: int
