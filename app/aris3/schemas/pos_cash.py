from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from app.aris3.schemas.pos_common import Money, PaginatedResponse, PosBaseModel


class OpenCashSessionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = None
    action: Literal['OPEN']
    opening_amount: Money
    business_date: date
    timezone: str
    reason: str | None = None


class CashInRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = None
    action: Literal['CASH_IN']
    amount: Money
    reason: str | None = None




class CashOutRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = None
    action: Literal['CASH_OUT']
    amount: Money
    reason: str | None = None

class CloseCashSessionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = None
    action: Literal['CLOSE']
    counted_cash: Money
    reason: str | None = None


PosCashSessionActionRequest = Annotated[
    OpenCashSessionRequest | CashInRequest | CashOutRequest | CloseCashSessionRequest,
    Field(discriminator='action'),
]


class PosCashCutQuoteRequest(PosBaseModel):
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = None
    cash_session_id: str | None = None
    use_last_cut_window: bool = True
    from_at: datetime | None = None
    to_at: datetime | None = None
    timezone: str | None = None
    cut_type: Literal["PARTIAL", "SHIFT_HANDOFF", "BANK_DEPOSIT"] = "PARTIAL"


class PosCashCutCreateRequest(PosCashCutQuoteRequest):
    transaction_id: str
    counted_cash: Money | None = None
    deposit_removed_amount: Money | None = None
    notes: str | None = None
    auto_apply_cash_out: bool = False


class PosCashCutActionRequest(PosBaseModel):
    transaction_id: str
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = None
    action: Literal["COMPLETE", "VOID", "PRINT_MARK", "APPLY_CASH_OUT"]
    amount: Money | None = None
    reason: str | None = None
    notes: str | None = None


class PosCashCutSummary(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    cash_session_id: str
    cut_number: int
    cut_type: str
    from_at: datetime
    to_at: datetime
    timezone: str
    opening_amount_snapshot: Money
    cash_sales_total: Money
    card_sales_total: Money
    transfer_sales_total: Money
    mixed_cash_component_total: Money
    mixed_card_component_total: Money
    mixed_transfer_component_total: Money
    cash_in_total: Money
    cash_out_total: Money
    cash_refunds_total: Money
    expected_cash: Money
    counted_cash: Money | None = None
    difference: Money | None = None
    deposit_removed_amount: Money | None = None
    deposit_cash_movement_id: str | None = None
    notes: str | None = None
    status: str
    created_by_user_id: str
    created_at: datetime
    completed_at: datetime | None = None


class PosCashCutQuoteResponse(PosBaseModel):
    quote: PosCashCutSummary


class PosCashCutListResponse(PaginatedResponse):
    rows: list[PosCashCutSummary]


class PosCashCutDetailResponse(PosBaseModel):
    cut: PosCashCutSummary


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
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
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
