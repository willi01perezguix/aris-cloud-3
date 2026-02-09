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
    actor_user_id: str | None
    cash_session_id: str | None
    sale_id: str | None
    business_date: date
    timezone: str
    movement_type: str
    amount: Decimal
    expected_balance_before: Decimal | None
    expected_balance_after: Decimal | None
    transaction_id: str | None
    reason: str | None
    trace_id: str | None
    occurred_at: datetime
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
    counted_cash: Decimal | None = None


class PosCashDayCloseResponse(BaseModel):
    id: str
    tenant_id: str
    store_id: str
    business_date: date
    timezone: str
    status: str
    force_close: bool
    reason: str | None
    expected_cash: Decimal
    counted_cash: Decimal | None
    difference_amount: Decimal | None
    difference_type: str | None
    net_cash_sales: Decimal
    cash_refunds: Decimal
    net_cash_movement: Decimal
    day_close_difference: Decimal | None
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime


class PosCashDayCloseSummaryResponse(BaseModel):
    id: str
    tenant_id: str
    store_id: str
    business_date: date
    timezone: str
    status: str
    force_close: bool
    reason: str | None
    expected_cash: Decimal
    counted_cash: Decimal | None
    difference_amount: Decimal | None
    difference_type: str | None
    net_cash_sales: Decimal
    cash_refunds: Decimal
    net_cash_movement: Decimal
    day_close_difference: Decimal | None
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime


class PosCashDayCloseSummaryListResponse(BaseModel):
    rows: list[PosCashDayCloseSummaryResponse]
    total: int


class PosCashReconciliationBreakdownRow(BaseModel):
    movement_type: str
    total_amount: Decimal
    movement_count: int


class PosCashReconciliationBreakdownResponse(BaseModel):
    business_date: date
    timezone: str
    expected_cash: Decimal
    opening_amount: Decimal
    cash_in: Decimal
    cash_out: Decimal
    net_cash_movement: Decimal
    net_cash_sales: Decimal
    cash_refunds: Decimal
    day_close_difference: Decimal | None
    movements: list[PosCashReconciliationBreakdownRow]
