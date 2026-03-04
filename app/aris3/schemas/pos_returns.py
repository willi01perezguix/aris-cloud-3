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
    resolution: Literal["REFUND", "EXCHANGE"]


class ReturnQuoteRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    store_id: str
    sale_id: str
    items: list[ReturnItem]
    exchange_lines: list[SaleLineSelector] | None = None
    reason: str | None = None


class ReturnQuoteNormalizedLine(PosBaseModel):
    sale_line_id: str
    resolution: Literal["REFUND", "EXCHANGE"]
    qty: int
    unit_price: Money
    line_total: Money


class ExchangePreviewLine(PosBaseModel):
    line_type: Literal["EPC", "SKU"]
    sku: str | None = None
    epc: str | None = None
    qty: int
    unit_price: Money
    line_total: Money


class ReturnQuoteResponse(PosBaseModel):
    refund_total: Money
    exchange_total: Money
    restocking_fee_total: Money
    net_adjustment: Money
    settlement_direction: Literal["CUSTOMER_PAYS", "STORE_REFUNDS", "NONE"]
    normalized_lines: list[ReturnQuoteNormalizedLine]
    exchange_preview: list[ExchangePreviewLine]


class ReturnSummaryRow(PosBaseModel):
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


class ReturnDetailLine(PosBaseModel):
    sale_line_id: str
    resolution: Literal["REFUND", "EXCHANGE"]
    qty: int
    condition: str
    unit_price: Money
    line_total: Money


class ReturnSettlementPayment(PosBaseModel):
    method: Literal["CASH", "CARD", "TRANSFER"]
    amount: Money
    authorization_code: str | None = None
    bank_name: str | None = None
    voucher_number: str | None = None


class ExchangeSaleSummary(PosBaseModel):
    sale_id: str
    receipt_number: str | None = None
    total_due: Money
    paid_total: Money


class ReturnEvent(PosBaseModel):
    action: str
    at: datetime
    by_user_id: str | None = None


class ReturnDetail(ReturnSummaryRow):
    lines: list[ReturnDetailLine]
    settlement_payments: list[ReturnSettlementPayment]
    exchange_sale_summary: ExchangeSaleSummary | None = None
    events: list[ReturnEvent]


class ReturnListResponse(PaginatedResponse):
    rows: list[ReturnSummaryRow]


class ReturnEligibilityLine(PosBaseModel):
    sale_line_id: str
    line_type: Literal["EPC", "SKU"]
    sku: str | None = None
    epc: str | None = None
    sold_qty: int
    returned_qty: int
    returnable_qty: int
    unit_price: Money


class ReturnEligibilityResponse(PosBaseModel):
    sale_id: str
    receipt_number: str | None = None
    eligible: bool
    reason: str | None = None
    lines: list[ReturnEligibilityLine]
    allowed_settlement_methods: list[str]


class CompleteReturnActionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    action: Literal["COMPLETE"]
    settlement_payments: list[ReturnSettlementPayment] | None = None
    reason: str | None = None


class VoidReturnActionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(default=None, deprecated=True, description="Deprecated: tenant scope is resolved from JWT/context.")
    action: Literal["VOID"]
    reason: str


ReturnActionRequest = Annotated[CompleteReturnActionRequest | VoidReturnActionRequest, Field(discriminator="action")]
ReturnSummary = ReturnSummaryRow
