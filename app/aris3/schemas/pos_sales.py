from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PosSaleLineSnapshot(BaseModel):
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


class PosSaleLineCreate(BaseModel):
    line_type: Literal["EPC", "SKU"]
    qty: int = 1
    unit_price: Decimal
    snapshot: PosSaleLineSnapshot


class PosPaymentCreate(BaseModel):
    method: Literal["CASH", "CARD", "TRANSFER"]
    amount: Decimal
    authorization_code: str | None = None
    bank_name: str | None = None
    voucher_number: str | None = None


class PosSaleCreateRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    store_id: str
    lines: list[PosSaleLineCreate]


class PosSaleUpdateRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    lines: list[PosSaleLineCreate] | None = None


class PosSaleActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    action: Literal["checkout", "cancel"]
    payments: list[PosPaymentCreate] | None = None


class PosSaleHeaderResponse(BaseModel):
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


class PosSaleLineResponse(BaseModel):
    id: str
    line_type: str
    qty: int
    unit_price: Decimal
    line_total: Decimal
    snapshot: PosSaleLineSnapshot
    created_at: datetime


class PosPaymentResponse(BaseModel):
    id: str
    method: str
    amount: Decimal
    authorization_code: str | None
    bank_name: str | None
    voucher_number: str | None
    created_at: datetime


class PosPaymentSummary(BaseModel):
    method: str
    amount: Decimal


class PosSaleResponse(BaseModel):
    header: PosSaleHeaderResponse
    lines: list[PosSaleLineResponse]
    payments: list[PosPaymentResponse]
    payment_summary: list[PosPaymentSummary]


class PosSaleListResponse(BaseModel):
    rows: list[PosSaleResponse]
