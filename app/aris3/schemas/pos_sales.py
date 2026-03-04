from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class PosBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json")
    def serialize_decimals(self, value):
        if isinstance(value, Decimal):
            return format(value.quantize(Decimal("0.01")), "f")
        return value


class PosSaleLineSnapshot(PosBaseModel):
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
    epc: str | None
    location_code: str | None
    pool: str | None
    status: str | None
    location_is_vendible: bool
    image_asset_id: UUID | None
    image_url: str | None
    image_thumb_url: str | None
    image_source: str | None
    image_updated_at: datetime | None


class PosSaleLineCreate(PosBaseModel):
    line_type: Literal["EPC", "SKU"]
    qty: int = 1
    unit_price: Decimal
    snapshot: PosSaleLineSnapshot


class PosPaymentCreate(PosBaseModel):
    method: Literal["CASH", "CARD", "TRANSFER"]
    amount: Decimal
    authorization_code: str | None = None
    bank_name: str | None = None
    voucher_number: str | None = None


class PosSaleCreateRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    store_id: str | None = None
    lines: list[PosSaleLineCreate]


class PosSaleUpdateRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    lines: list[PosSaleLineCreate] | None = None


class PosReturnItem(PosBaseModel):
    line_id: str
    qty: int = 1
    condition: str


class PosSaleActionRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    action: Literal["checkout", "cancel", "REFUND_ITEMS", "EXCHANGE_ITEMS"]
    payments: list[PosPaymentCreate] | None = None
    refund_payments: list[PosPaymentCreate] | None = None
    return_items: list[PosReturnItem] | None = None
    exchange_lines: list[PosSaleLineCreate] | None = None
    receipt_number: str | None = None
    manager_override: bool | None = None


class PosSaleHeaderResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    status: str
    total_due: Decimal
    paid_total: Decimal
    balance_due: Decimal
    change_due: Decimal
    created_by_user_id: str | None
    updated_by_user_id: str | None
    checked_out_by_user_id: str | None
    canceled_by_user_id: str | None
    checked_out_at: datetime | None
    canceled_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class PosSaleLineResponse(PosBaseModel):
    id: str
    line_type: str
    qty: int
    unit_price: Decimal
    line_total: Decimal
    snapshot: PosSaleLineSnapshot
    created_at: datetime


class PosPaymentResponse(PosBaseModel):
    id: str
    method: str
    amount: Decimal
    authorization_code: str | None
    bank_name: str | None
    voucher_number: str | None
    created_at: datetime


class PosPaymentSummary(PosBaseModel):
    method: str
    amount: Decimal


class PosReturnTotals(PosBaseModel):
    subtotal: Decimal
    restocking_fee: Decimal
    total: Decimal


class PosReturnEventSummary(PosBaseModel):
    id: str
    action: str
    refund_total: Decimal
    exchange_total: Decimal
    net_adjustment: Decimal
    created_at: datetime


class PosSaleResponse(PosBaseModel):
    header: PosSaleHeaderResponse
    lines: list[PosSaleLineResponse]
    payments: list[PosPaymentResponse]
    payment_summary: list[PosPaymentSummary]
    refunded_totals: PosReturnTotals
    exchanged_totals: PosReturnTotals
    net_adjustment: Decimal
    return_events: list[PosReturnEventSummary]


class PosSaleListResponse(PosBaseModel):
    rows: list[PosSaleResponse]
