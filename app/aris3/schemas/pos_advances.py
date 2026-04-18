from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.aris3.schemas.pos_sales import POSMoney, PosBaseModel, money_field


class PosAdvanceCreateRequest(PosBaseModel):
    transaction_id: str
    store_id: str
    customer_name: str = Field(min_length=1, max_length=255)
    amount: POSMoney = money_field("100.00")
    payment_method: Literal["CASH", "CARD", "TRANSFER"]
    voucher_type: Literal["ADVANCE", "GIFT_CARD"] = "ADVANCE"
    notes: str | None = None


class PosAdvanceActionRequest(PosBaseModel):
    transaction_id: str
    action: Literal["REFUND", "EXPIRE_NOW", "CONSUME"]
    refund_method: Literal["CASH", "CARD", "TRANSFER"] | None = None
    sale_total: POSMoney | None = Field(default=None, description="Total de venta para validar consumo completo", examples=["250.00"])
    sale_id: str | None = None
    reason: str | None = None


class PosAdvanceEventResponse(PosBaseModel):
    id: str
    action: str
    payload: dict | None = None
    created_by_user_id: str | None = None
    created_at: datetime


class PosAdvanceSummary(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    advance_number: int
    barcode_value: str
    voucher_type: str = "ADVANCE"
    customer_name: str
    issued_amount: POSMoney = money_field("100.00")
    issued_payment_method: str
    issued_cash_movement_id: str | None = None
    issued_at: datetime
    expires_at: datetime
    status: str
    consumed_sale_id: str | None = None
    refunded_cash_movement_id: str | None = None
    refunded_at: datetime | None = None
    expired_at: datetime | None = None
    notes: str | None = None
    created_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class PosAdvanceDetailResponse(PosAdvanceSummary):
    events: list[PosAdvanceEventResponse] = []
    store_name: str | None = None
    barcode_type: str = "CODE128"
    legal_notice: str | None = None
    applied_amount: POSMoney | None = Field(default=None, description="Monto aplicado del anticipo", examples=["100.00"])
    remaining_amount_to_charge: POSMoney | None = Field(default=None, description="Monto restante por cobrar en la venta", examples=["150.00"])
    drawer_open_required: bool = False


class PosAdvanceListResponse(PosBaseModel):
    page: int
    page_size: int
    total: int
    rows: list[PosAdvanceSummary]


class PosAdvanceLookupResponse(PosBaseModel):
    found: bool
    advance: PosAdvanceSummary | None = None


class PosAdvanceAlertsResponse(PosBaseModel):
    as_of: datetime
    days: int
    total: int
    rows: list["PosAdvanceAlertRow"]


class PosAdvanceAlertRow(PosBaseModel):
    id: str
    advance_number: int
    customer_name: str
    amount: POSMoney = money_field("100.00")
    issued_at: datetime
    expires_at: datetime
    days_to_expiry: int
    status: str


class PosAdvanceSweepResponse(PosBaseModel):
    expired_count: int
    expired_ids: list[str]
    as_of: datetime
