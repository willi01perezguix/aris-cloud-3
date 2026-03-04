from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema, field_serializer


POSMoney = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value.quantize(Decimal("0.01")), "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number"},
                {"type": "string", "pattern": r"^-?\d{1,10}(?:\.\d{1,2})?$"},
            ]
        },
        mode="validation",
    ),
    WithJsonSchema({"type": "string", "pattern": r"^-?\d{1,10}(?:\.\d{2})?$"}, mode="serialization"),
]

_MONEY_FIELD_DESCRIPTION = "Acepta number o string decimal; se serializa como string con dos decimales"


def money_field(*examples: str) -> Field:
    return Field(description=_MONEY_FIELD_DESCRIPTION, examples=list(examples) or ["0.00", "25.00", "125.50", "-10.00"])


class PosBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json")
    def serialize_decimals(self, value):
        if isinstance(value, Decimal):
            return format(value.quantize(Decimal("0.01")), "f")
        return value


class PosCashSessionActionRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    store_id: str | None = None
    action: Literal["OPEN", "CASH_IN", "CASH_OUT", "CLOSE"] = Field(
        description="Acciones permitidas: OPEN, CASH_IN, CASH_OUT, CLOSE"
    )
    opening_amount: POSMoney | None = money_field("0.00", "25.00")
    amount: POSMoney | None = money_field("25.00", "125.50")
    counted_cash: POSMoney | None = money_field("0.00", "125.50")
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
    opening_amount: POSMoney = money_field("0.00", "25.00")
    expected_cash: POSMoney = money_field("0.00", "125.50")
    counted_cash: POSMoney | None = money_field("0.00", "125.50")
    difference: POSMoney | None = money_field("-10.00", "0.00", "25.00")
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
    amount: POSMoney = money_field("25.00", "125.50", "-10.00")
    expected_balance_before: POSMoney | None = money_field("0.00", "125.50")
    expected_balance_after: POSMoney | None = money_field("0.00", "125.50")
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
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    store_id: str
    action: Literal["CLOSE_DAY"] = "CLOSE_DAY"
    business_date: date
    timezone: str
    force_if_open_sessions: bool | None = None
    reason: str | None = None
    counted_cash: POSMoney | None = money_field("0.00", "125.50")


class PosCashDayCloseResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    business_date: date
    timezone: str
    status: str
    force_close: bool
    reason: str | None
    expected_cash: POSMoney = money_field("0.00", "125.50")
    counted_cash: POSMoney | None = money_field("0.00", "125.50")
    difference_amount: POSMoney | None = money_field("-10.00", "0.00", "25.00")
    difference_type: str | None
    net_cash_sales: POSMoney = money_field("0.00", "125.50")
    cash_refunds: POSMoney = money_field("0.00", "25.00")
    net_cash_movement: POSMoney = money_field("-10.00", "0.00", "25.00")
    day_close_difference: POSMoney | None = money_field("-10.00", "0.00", "25.00")
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
    expected_cash: POSMoney = money_field("0.00", "125.50")
    counted_cash: POSMoney | None = money_field("0.00", "125.50")
    difference_amount: POSMoney | None = money_field("-10.00", "0.00", "25.00")
    difference_type: str | None
    net_cash_sales: POSMoney = money_field("0.00", "125.50")
    cash_refunds: POSMoney = money_field("0.00", "25.00")
    net_cash_movement: POSMoney = money_field("-10.00", "0.00", "25.00")
    day_close_difference: POSMoney | None = money_field("-10.00", "0.00", "25.00")
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime


class PosCashDayCloseSummaryListResponse(PosBaseModel):
    rows: list[PosCashDayCloseSummaryResponse]
    total: int


class PosCashReconciliationBreakdownRow(PosBaseModel):
    movement_type: str
    total_amount: POSMoney = money_field("-10.00", "0.00", "125.50")
    movement_count: int


class PosCashReconciliationBreakdownResponse(PosBaseModel):
    business_date: date
    timezone: str
    expected_cash: POSMoney = money_field("0.00", "125.50")
    opening_amount: POSMoney = money_field("0.00", "25.00")
    cash_in: POSMoney = money_field("0.00", "125.50")
    cash_out: POSMoney = money_field("0.00", "125.50")
    net_cash_movement: POSMoney = money_field("-10.00", "0.00", "25.00")
    net_cash_sales: POSMoney = money_field("0.00", "125.50")
    cash_refunds: POSMoney = money_field("0.00", "25.00")
    day_close_difference: POSMoney | None = money_field("-10.00", "0.00", "25.00")
    movements: list[PosCashReconciliationBreakdownRow]
