from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from app.aris3.schemas.pos_common import Money, PaginatedResponse, PosBaseModel


class Snapshot(PosBaseModel):
    sku: str | None = None
    description: str | None = None
    epc: str | None = None


class SaleLineSelectorEpc(PosBaseModel):
    line_type: Literal['EPC']
    epc: str


class SaleLineSelectorSku(PosBaseModel):
    line_type: Literal['SKU']
    sku: str
    qty: int = Field(default=1, ge=1)


SaleLineSelector = Annotated[SaleLineSelectorEpc | SaleLineSelectorSku, Field(discriminator='line_type')]


class Payment(PosBaseModel):
    method: Literal['CASH', 'CARD', 'TRANSFER']
    amount: Money


class PaymentSummary(PosBaseModel):
    method: str
    amount: Money


class SaleCreateRequest(PosBaseModel):
    transaction_id: str
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    store_id: str
    lines: list[SaleLineSelector]


class SaleReplaceDraftRequest(SaleCreateRequest):
    pass


class SaleCheckoutAction(PosBaseModel):
    transaction_id: str
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    action: Literal['CHECKOUT']
    payments: list[Payment]


class SaleCancelAction(PosBaseModel):
    transaction_id: str
    tenant_id: Annotated[str | None, Field(deprecated=True)] = None
    action: Literal['CANCEL']
    reason: str | None = None


SaleActionRequest = Annotated[SaleCheckoutAction | SaleCancelAction, Field(discriminator='action')]


class SaleLine(PosBaseModel):
    id: str
    line_type: str
    qty: int
    unit_price: Money
    line_total: Money
    returned_qty: int = 0
    returnable_qty: int = 0
    snapshot: Snapshot


class SaleSummary(PosBaseModel):
    id: str
    receipt_number: str | None = None
    store_id: str
    status: str
    business_date: date | None = None
    timezone: str | None = None
    total_due: Money
    paid_total: Money
    balance_due: Money
    item_count: int
    payment_summary: list[PaymentSummary]
    checked_out_at: datetime | None = None
    created_at: datetime


class SaleDetail(SaleSummary):
    lines: list[SaleLine]
    payments: list[Payment]
    return_summary: dict | None = None
    return_events: list[dict] = []


class SaleListResponse(PaginatedResponse):
    rows: list[SaleSummary]

# backward-compatible aliases used by existing router implementation
PosPaymentCreate = Payment
PosPaymentResponse = Payment
PosPaymentSummary = PaymentSummary
PosReturnEventSummary = dict
PosReturnItem = dict
PosReturnTotals = dict
PosSaleActionRequest = SaleActionRequest
PosSaleCreateRequest = SaleCreateRequest
PosSaleHeaderResponse = SaleSummary
PosSaleLineCreate = SaleLineSelector
PosSaleLineResponse = SaleLine
PosSaleLineSnapshot = Snapshot
PosSaleListResponse = SaleListResponse
PosSaleResponse = SaleDetail
PosSaleUpdateRequest = SaleReplaceDraftRequest
