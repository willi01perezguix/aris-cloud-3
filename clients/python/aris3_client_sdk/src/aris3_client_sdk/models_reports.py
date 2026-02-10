from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

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
    granularity: str | None = None
    business_date_mode: str | None = None
    sort_by: str | None = None
    sort_dir: str | None = None
    page: int | None = None
    page_size: int | None = None
    currency: str | None = None


def validate_date_range(from_value: date | datetime | str | None, to_value: date | datetime | str | None) -> None:
    if from_value is None or to_value is None:
        return
    start = _coerce_report_date(from_value)
    end = _coerce_report_date(to_value)
    if start > end:
        raise ValueError("from/to date range is invalid: 'from' must be less than or equal to 'to'")


def normalize_report_filters(filters: ReportFilter | dict[str, Any] | None) -> ReportFilter:
    if filters is None:
        return ReportFilter()
    payload = filters.model_dump(by_alias=True, exclude_none=True, mode="json") if isinstance(filters, ReportFilter) else dict(filters)

    store_ids = payload.pop("store_ids", None)
    if payload.get("store_id") is None and isinstance(store_ids, list) and store_ids:
        payload["store_id"] = store_ids[0]
    if payload.get("from") is None and payload.get("date_from"):
        payload["from"] = payload.pop("date_from")
    if payload.get("to") is None and payload.get("date_to"):
        payload["to"] = payload.pop("date_to")
    if payload.get("grouping") is None and payload.get("granularity"):
        payload["grouping"] = payload.get("granularity")

    parsed = ReportFilter.model_validate(payload)
    validate_date_range(parsed.from_value, parsed.to_value)
    return parsed


def _coerce_report_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    clean = value.strip()
    if "T" in clean:
        return datetime.fromisoformat(clean.replace("Z", "+00:00")).date()
    return date.fromisoformat(clean)


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


class ReportTrendRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str
    business_date: date | None = None
    net_sales: Decimal | None = None
    net_profit: Decimal | None = None
    orders_paid_count: int | None = None


class ReportBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    label: str | None = None
    value: Decimal | int | str | None = None
    percentage: Decimal | None = None


class ReportProfitSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: ReportMeta
    totals: ReportTotals
