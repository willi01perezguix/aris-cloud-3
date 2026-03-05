from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer


def normalize_money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


class ReportModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_fields(self, value):
        if isinstance(value, Decimal):
            return normalize_money(value)
        return value


class ReportTotals(ReportModel):
    gross_sales: Decimal
    refunds_total: Decimal
    net_sales: Decimal
    cogs_gross: Decimal
    cogs_reversed_from_returns: Decimal
    net_cogs: Decimal
    net_profit: Decimal
    orders_paid_count: int
    average_ticket: Decimal


class ReportMeta(ReportModel):
    store_id: str
    timezone: str
    from_datetime: datetime = Field(..., description="Inclusive start datetime")
    to_datetime: datetime = Field(..., description="Inclusive end datetime")
    trace_id: str | None
    query_ms: float
    filters: dict


class ReportOverviewResponse(ReportModel):
    meta: ReportMeta
    totals: ReportTotals


class DailyRow(ReportModel):
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


class ReportDailyResponse(ReportModel):
    meta: ReportMeta
    totals: ReportTotals
    rows: list[DailyRow]


class CalendarRow(ReportModel):
    business_date: date
    net_sales: Decimal
    net_profit: Decimal
    orders_paid_count: int


class ReportCalendarResponse(ReportModel):
    meta: ReportMeta
    totals: ReportTotals
    rows: list[CalendarRow]


ReportDailyRow = DailyRow
ReportCalendarDay = CalendarRow
