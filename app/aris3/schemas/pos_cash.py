from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from app.aris3.schemas.pos_common import Money, PaginatedResponse, PosBaseModel


class OpenCashSessionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    store_id: str | None = None
    action: Literal['OPEN']
    opening_amount: Money
    business_date: date
    timezone: str


class CashInRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    store_id: str | None = None
    action: Literal['CASH_IN']
    amount: Money
    reason: str




class CashOutRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    store_id: str | None = None
    action: Literal['CASH_OUT']
    amount: Money
    reason: str

class CloseCashSessionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    store_id: str | None = None
    action: Literal['CLOSE']
    counted_cash: Money


PosCashSessionActionRequest = Annotated[
    OpenCashSessionRequest | CashInRequest | CashOutRequest | CloseCashSessionRequest,
    Field(discriminator='action'),
]


class PosCashSessionSummary(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str | None = None
    cashier_user_id: str
    status: str
    business_date: date
    timezone: str
    opening_amount: Money
    expected_cash: Money
    counted_cash: Money | None = None
    difference: Money | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    created_at: datetime


class PosCashSessionCurrentResponse(PosBaseModel):
    session: PosCashSessionSummary | None


class PosCashMovementResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    cashier_user_id: str
    actor_user_id: str | None = None
    cash_session_id: str | None = None
    sale_id: str | None = None
    business_date: date
    timezone: str
    movement_type: str
    amount: Money
    expected_balance_before: Money | None = None
    expected_balance_after: Money | None = None
    transaction_id: str | None = None
    reason: str | None = None
    trace_id: str | None = None
    occurred_at: datetime
    created_at: datetime


class PosCashMovementListResponse(PaginatedResponse):
    rows: list[PosCashMovementResponse]


class PosCashDayCloseActionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    store_id: str
    action: Literal['CLOSE_DAY'] = 'CLOSE_DAY'
    business_date: date
    timezone: str
    force_if_open_sessions: bool | None = None
    reason: str | None = None
    counted_cash: Money | None = None


class PosCashDayCloseResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    business_date: date
    timezone: str
    status: str
    force_close: bool
    reason: str | None = None
    expected_cash: Money
    counted_cash: Money | None = None
    difference_amount: Money | None = None
    difference_type: str | None = None
    net_cash_sales: Money
    cash_refunds: Money
    net_cash_movement: Money
    day_close_difference: Money | None = None
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime


class PosCashDayCloseSummaryResponse(PosCashDayCloseResponse):
    pass


class PosCashDayCloseSummaryListResponse(PaginatedResponse):
    rows: list[PosCashDayCloseSummaryResponse]


class PosCashReconciliationBreakdownRow(PosBaseModel):
    movement_type: str
    total_amount: Money
    movement_count: int


class PosCashReconciliationBreakdownResponse(PosBaseModel):
    business_date: date
    timezone: str
    expected_cash: Money
    opening_amount: Money
    cash_in: Money
    cash_out: Money
    net_cash_movement: Money
    net_cash_sales: Money
    cash_refunds: Money
    day_close_difference: Money | None = None
    movements: list[PosCashReconciliationBreakdownRow]
