from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReportFilter(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    store_id: str | None = None
    from_value: date | datetime | str | None = Field(default=None, alias="from")
    to_value: date | datetime | str | None = Field(default=None, alias="to")
    timezone: str | None = None
    cashier: str | None = None
    channel: str | None = None
    payment_method: str | None = None
    grouping: str | None = None
    currency: str | None = None


class ReportMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    store_id: str
    timezone: str
    from_datetime: datetime
    to_datetime: datetime
    trace_id: str | None = None
    query_ms: float | None = None
    filters: dict[str, object] = Field(default_factory=dict)


class ReportTotals(BaseModel):
    model_config = ConfigDict(extra="allow")

    gross_sales: Decimal
    refunds_total: Decimal
    net_sales: Decimal
    cogs_gross: Decimal
    cogs_reversed_from_returns: Decimal
    net_cogs: Decimal
    net_profit: Decimal
    orders_paid_count: int
    average_ticket: Decimal


class ReportOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: ReportMeta
    totals: ReportTotals


class ReportDailyRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    business_date: date
    gross_sales: Decimal
    refunds_total: Decimal
    net_sales: Decimal
    cogs_gross: Decimal
    cogs_reversed_from_returns: Decimal
    net_cogs: Decimal
    net_profit: Decimal
    orders_paid_count: int
    average_ticket: Decimal


class ReportDailyResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: ReportMeta
    totals: ReportTotals
    rows: list[ReportDailyRow]


class ReportCalendarRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    business_date: date
    net_sales: Decimal
    net_profit: Decimal
    orders_paid_count: int


class ReportCalendarResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: ReportMeta
    totals: ReportTotals
    rows: list[ReportCalendarRow]


class ReportProfitSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: ReportMeta
    totals: ReportTotals
