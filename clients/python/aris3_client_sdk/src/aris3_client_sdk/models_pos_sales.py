from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PosSaleLineSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    status: str | None = None
    location_is_vendible: bool | None = None
    image_asset_id: str | None = None
    image_url: str | None = None
    image_thumb_url: str | None = None
    image_source: str | None = None
    image_updated_at: datetime | None = None


class PosSaleLineCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    line_type: Literal["EPC", "SKU"]
    qty: int = 1
    unit_price: Decimal
    snapshot: PosSaleLineSnapshot


class PosPaymentBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: Literal["CASH", "CARD", "TRANSFER"]
    amount: Decimal


class PosPaymentCash(PosPaymentBase):
    model_config = ConfigDict(extra="allow")

    method: Literal["CASH"] = "CASH"


class PosPaymentCard(PosPaymentBase):
    model_config = ConfigDict(extra="allow")

    method: Literal["CARD"] = "CARD"
    authorization_code: str


class PosPaymentTransfer(PosPaymentBase):
    model_config = ConfigDict(extra="allow")

    method: Literal["TRANSFER"] = "TRANSFER"
    bank_name: str
    voucher_number: str


class PosPaymentCreate(PosPaymentBase):
    model_config = ConfigDict(extra="allow")

    authorization_code: str | None = None
    bank_name: str | None = None
    voucher_number: str | None = None


class PosSaleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    store_id: str
    lines: list[PosSaleLineCreate]


class PosSaleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    lines: list[PosSaleLineCreate] | None = None


class PosSaleActionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    action: Literal["checkout", "cancel", "REFUND_ITEMS", "EXCHANGE_ITEMS"]
    payments: list[PosPaymentCreate] | None = None
    refund_payments: list[PosPaymentCreate] | None = None
    return_items: list[dict] | None = None
    exchange_lines: list[PosSaleLineCreate] | None = None
    receipt_number: str | None = None
    manager_override: bool | None = None


class PosSaleHeader(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    tenant_id: str | None = None
    store_id: str | None = None
    status: str | None = None
    total_due: Decimal | None = None
    paid_total: Decimal | None = None
    balance_due: Decimal | None = None
    change_due: Decimal | None = None
    created_by_user_id: str | None = None
    updated_by_user_id: str | None = None
    checked_out_by_user_id: str | None = None
    canceled_by_user_id: str | None = None
    checked_out_at: datetime | None = None
    canceled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PosSaleTotals(BaseModel):
    model_config = ConfigDict(extra="allow")

    subtotal: Decimal | None = None
    discount: Decimal | None = None
    tax: Decimal | None = None
    total_due: Decimal | None = None
    paid_total: Decimal | None = None
    balance_due: Decimal | None = None
    change_due: Decimal | None = None


class PosSaleLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    line_type: str | None = None
    qty: int | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    snapshot: PosSaleLineSnapshot | None = None
    created_at: datetime | None = None


class PosPaymentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    method: str | None = None
    amount: Decimal | None = None
    authorization_code: str | None = None
    bank_name: str | None = None
    voucher_number: str | None = None
    created_at: datetime | None = None


class PosPaymentSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: str | None = None
    amount: Decimal | None = None


class PosReturnTotals(BaseModel):
    model_config = ConfigDict(extra="allow")

    subtotal: Decimal | None = None
    restocking_fee: Decimal | None = None
    total: Decimal | None = None


class PosReturnEventSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    action: str | None = None
    refund_total: Decimal | None = None
    exchange_total: Decimal | None = None
    net_adjustment: Decimal | None = None
    created_at: datetime | None = None


class PosSaleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    header: PosSaleHeader
    lines: list[PosSaleLine] = Field(default_factory=list)
    payments: list[PosPaymentResponse] = Field(default_factory=list)
    payment_summary: list[PosPaymentSummary] = Field(default_factory=list)
    refunded_totals: PosReturnTotals | None = None
    exchanged_totals: PosReturnTotals | None = None
    net_adjustment: Decimal | None = None
    return_events: list[PosReturnEventSummary] = Field(default_factory=list)


class PosSaleListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: list[PosSaleResponse]


class PosSaleQuery(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    tenant_id: str | None = None
    store_id: str | None = None
    status: str | None = None
    from_date: datetime | str | None = Field(default=None, alias="from")
    to_date: datetime | str | None = Field(default=None, alias="to")
