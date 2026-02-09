from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class ReportTotals(BaseModel):
    gross_sales: Decimal
    refunds_total: Decimal
    net_sales: Decimal
    cogs_gross: Decimal
    cogs_reversed_from_returns: Decimal
    net_cogs: Decimal
    net_profit: Decimal
    orders_paid_count: int
    average_ticket: Decimal


class ReportMeta(BaseModel):
    store_id: str
    timezone: str
    from_datetime: datetime
    to_datetime: datetime
    trace_id: str | None
    query_ms: float
    filters: dict


class ReportOverviewResponse(BaseModel):
    meta: ReportMeta
    totals: ReportTotals


class ReportDailyRow(BaseModel):
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
    meta: ReportMeta
    totals: ReportTotals
    rows: list[ReportDailyRow]


class ReportCalendarDay(BaseModel):
    business_date: date
    net_sales: Decimal
    net_profit: Decimal
    orders_paid_count: int


class ReportCalendarResponse(BaseModel):
    meta: ReportMeta
    totals: ReportTotals
    rows: list[ReportCalendarDay]
