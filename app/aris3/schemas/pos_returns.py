from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from app.aris3.schemas.pos_common import Money, PaginatedResponse, PosBaseModel
from app.aris3.schemas.pos_sales import SaleLineSelector


class ReturnItem(PosBaseModel):
    sale_line_id: str
    qty: int = Field(ge=1)
    condition: str
    resolution: Literal['REFUND', 'EXCHANGE']


class ReturnQuoteRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None)
    store_id: str
    sale_id: str
    items: list[ReturnItem]
    exchange_lines: list[SaleLineSelector] | None = None
    reason: str | None = None


class ReturnQuoteResponse(PosBaseModel):
    refund_total: Money
    exchange_total: Money
    restocking_fee_total: Money
    net_adjustment: Money
    settlement_direction: Literal['CUSTOMER_PAYS', 'STORE_REFUNDS', 'NONE']
    normalized_lines: list[dict]
    exchange_preview: list[dict]


class ReturnSummary(PosBaseModel):
    id: str
    return_number: str
    sale_id: str
    original_receipt_number: str | None = None
    store_id: str
    status: str
    return_type: str
    refund_total: Money
    exchange_total: Money
    net_adjustment: Money
    settlement_direction: str
    business_date: date | None = None
    timezone: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ReturnDetail(ReturnSummary):
    lines: list[dict]
    settlement_payments: list[dict]
    exchange_sale_summary: dict | None = None
    events: list[dict]


class ReturnListResponse(PaginatedResponse):
    rows: list[ReturnSummary]


class ReturnEligibilityResponse(PosBaseModel):
    sale_id: str
    receipt_number: str | None = None
    eligible: bool
    reason: str | None = None
    lines: list[dict]
    allowed_settlement_methods: list[str]


class ReturnCompleteAction(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = None
    action: Literal['COMPLETE']
    settlement_payments: list[dict] | None = None
    reason: str | None = None


class ReturnVoidAction(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = None
    action: Literal['VOID']
    reason: str


ReturnActionRequest = Annotated[ReturnCompleteAction | ReturnVoidAction, Field(discriminator='action')]
