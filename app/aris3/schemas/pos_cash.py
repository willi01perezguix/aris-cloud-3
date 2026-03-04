from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class PosBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json")
    def serialize_decimals(self, value):
        if isinstance(value, Decimal):
            return format(value.quantize(Decimal("0.01")), "f")
        return value




class PosCashSessionActionRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, deprecated=True)
    store_id: str | None = None
    action: Literal["OPEN", "CASH_IN", "CASH_OUT", "CLOSE"] = Field(
        description="Allowed cash session actions: OPEN, CASH_IN, CASH_OUT, CLOSE"
    )
    opening_amount: Decimal | None = Field(default=None, examples=["125.50"])
    amount: Decimal | None = Field(default=None, examples=["25.00"])
    counted_cash: Decimal | None = Field(default=None, examples=["125.50"])
    business_date: date | None = None
    timezone: str | None = None
    reason: str | None = None


class PosCashSessionSummary(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str | None = None
    cashier_user_id: str
    status: str
    business_date: date
    timezone: str
    opening_amount: Decimal = Field(examples=["125.50"])
    expected_cash: Decimal = Field(examples=["125.50"])
    counted_cash: Decimal | None = Field(examples=["125.50"])
    difference: Decimal | None = Field(examples=["0.00"])
    opened_at: datetime
    closed_at: datetime | None
    created_at: datetime


class PosCashSessionCurrentResponse(PosBaseModel):
    session: PosCashSessionSummary | None


class PosCashMovementResponse(PosBaseModel):
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
    amount: Decimal = Field(examples=["25.00"])
    expected_balance_before: Decimal | None = Field(examples=["100.00"])
    expected_balance_after: Decimal | None = Field(examples=["125.00"])
    transaction_id: str | None
    reason: str | None
    trace_id: str | None
    occurred_at: datetime
    created_at: datetime


class PosCashMovementListResponse(PosBaseModel):
    rows: list[PosCashMovementResponse]
    total: int


class PosCashDayCloseActionRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, deprecated=True)
    store_id: str
    action: Literal["CLOSE_DAY"] = "CLOSE_DAY"
    business_date: date
    timezone: str
    force_if_open_sessions: bool | None = None
    reason: str | None = None
    counted_cash: Decimal | None = Field(default=None, examples=["125.50"])


class PosCashDayCloseResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    business_date: date
    timezone: str
    status: str
    force_close: bool
    reason: str | None
    expected_cash: Decimal = Field(examples=["125.50"])
    counted_cash: Decimal | None = Field(examples=["125.50"])
    difference_amount: Decimal | None = Field(examples=["0.00"])
    difference_type: str | None
    net_cash_sales: Decimal = Field(examples=["250.00"])
    cash_refunds: Decimal = Field(examples=["25.00"])
    net_cash_movement: Decimal = Field(examples=["100.00"])
    day_close_difference: Decimal | None = Field(examples=["0.00"])
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime


class PosCashDayCloseSummaryResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    business_date: date
    timezone: str
    status: str
    force_close: bool
    reason: str | None
    expected_cash: Decimal = Field(examples=["125.50"])
    counted_cash: Decimal | None = Field(examples=["125.50"])
    difference_amount: Decimal | None = Field(examples=["0.00"])
    difference_type: str | None
    net_cash_sales: Decimal = Field(examples=["250.00"])
    cash_refunds: Decimal = Field(examples=["25.00"])
    net_cash_movement: Decimal = Field(examples=["100.00"])
    day_close_difference: Decimal | None = Field(examples=["0.00"])
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime


class PosCashDayCloseSummaryListResponse(PosBaseModel):
    rows: list[PosCashDayCloseSummaryResponse]
    total: int


class PosCashReconciliationBreakdownRow(PosBaseModel):
    movement_type: str
    total_amount: Decimal = Field(examples=["25.00"])
    movement_count: int


class PosCashReconciliationBreakdownResponse(PosBaseModel):
    business_date: date
    timezone: str
    expected_cash: Decimal = Field(examples=["125.50"])
    opening_amount: Decimal = Field(examples=["100.00"])
    cash_in: Decimal = Field(examples=["50.00"])
    cash_out: Decimal = Field(examples=["24.50"])
    net_cash_movement: Decimal = Field(examples=["25.50"])
    net_cash_sales: Decimal = Field(examples=["250.00"])
    cash_refunds: Decimal = Field(examples=["25.00"])
    day_close_difference: Decimal | None = Field(examples=["0.00"])
    movements: list[PosCashReconciliationBreakdownRow]
