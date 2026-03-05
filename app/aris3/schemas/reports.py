from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "gross_sales": "1540.75",
                "refunds_total": "20.00",
                "net_sales": "1520.75",
                "cogs_gross": "500.00",
                "cogs_reversed_from_returns": "5.00",
                "net_cogs": "495.00",
                "net_profit": "1025.75",
                "orders_paid_count": 42,
                "average_ticket": "36.21",
            }
        }
    )


class ReportFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    store_id: str
    from_value: str = Field(..., alias="from", description="ISO 8601/date, inclusive start")
    to_value: str = Field(..., alias="to", description="ISO 8601/date, inclusive end")
    timezone: str = Field(..., description="Timezone used to resolve date boundaries. Defaults to UTC when omitted.")
    cashier: str | None = None
    channel: str | None = None
    payment_method: str | None = None


class ReportMeta(ReportModel):
    store_id: str
    timezone: str
    from_datetime: datetime = Field(..., description="Inclusive start datetime")
    to_datetime: datetime = Field(..., description="Inclusive end datetime")
    trace_id: str | None
    query_ms: float
    filters: ReportFilters

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                "timezone": "America/Mexico_City",
                "from_datetime": "2026-03-01T00:00:00-06:00",
                "to_datetime": "2026-03-01T23:59:59.999999-06:00",
                "trace_id": "trace-reports-overview-001",
                "query_ms": 12.8,
                "filters": {
                    "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                    "from": "2026-03-01T00:00:00-06:00",
                    "to": "2026-03-01T23:59:59.999999-06:00",
                    "timezone": "America/Mexico_City",
                    "cashier": "cashier-1",
                },
            }
        }
    )


class ReportOverviewResponse(ReportModel):
    meta: ReportMeta
    totals: ReportTotals


class ReportDailyRow(ReportModel):
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "business_date": "2026-03-01",
                "gross_sales": "1540.75",
                "refunds_total": "20.00",
                "net_sales": "1520.75",
                "cogs_gross": "500.00",
                "cogs_reversed_from_returns": "5.00",
                "net_cogs": "495.00",
                "net_profit": "1025.75",
                "orders_paid_count": 42,
                "average_ticket": "36.21",
            }
        }
    )


class ReportDailyResponse(ReportModel):
    meta: ReportMeta
    totals: ReportTotals
    rows: list[ReportDailyRow]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "meta": {
                    "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                    "timezone": "America/Mexico_City",
                    "from_datetime": "2026-03-01T00:00:00-06:00",
                    "to_datetime": "2026-03-03T23:59:59.999999-06:00",
                    "trace_id": "trace-reports-daily-001",
                    "query_ms": 12.8,
                    "filters": {
                        "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                        "from": "2026-03-01T00:00:00-06:00",
                        "to": "2026-03-03T23:59:59.999999-06:00",
                        "timezone": "America/Mexico_City",
                    },
                },
                "totals": {
                    "gross_sales": "1540.75",
                    "refunds_total": "20.00",
                    "net_sales": "1520.75",
                    "cogs_gross": "500.00",
                    "cogs_reversed_from_returns": "5.00",
                    "net_cogs": "495.00",
                    "net_profit": "1025.75",
                    "orders_paid_count": 42,
                    "average_ticket": "36.21",
                },
                "rows": [
                    {
                        "business_date": "2026-03-01",
                        "gross_sales": "520.25",
                        "refunds_total": "10.00",
                        "net_sales": "510.25",
                        "cogs_gross": "170.00",
                        "cogs_reversed_from_returns": "2.50",
                        "net_cogs": "167.50",
                        "net_profit": "342.75",
                        "orders_paid_count": 15,
                        "average_ticket": "34.02",
                    }
                ],
            }
        }
    )


class ReportCalendarRow(ReportModel):
    business_date: date
    net_sales: Decimal
    net_profit: Decimal
    orders_paid_count: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "business_date": "2026-03-02",
                "net_sales": "490.50",
                "net_profit": "331.00",
                "orders_paid_count": 14,
            }
        }
    )


class ReportCalendarResponse(ReportModel):
    meta: ReportMeta
    totals: ReportTotals
    rows: list[ReportCalendarRow]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "meta": {
                    "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                    "timezone": "America/Mexico_City",
                    "from_datetime": "2026-03-01T00:00:00-06:00",
                    "to_datetime": "2026-03-03T23:59:59.999999-06:00",
                    "trace_id": "trace-reports-calendar-001",
                    "query_ms": 11.3,
                    "filters": {
                        "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                        "from": "2026-03-01T00:00:00-06:00",
                        "to": "2026-03-03T23:59:59.999999-06:00",
                        "timezone": "America/Mexico_City",
                    },
                },
                "totals": {
                    "gross_sales": "1540.75",
                    "refunds_total": "20.00",
                    "net_sales": "1520.75",
                    "cogs_gross": "500.00",
                    "cogs_reversed_from_returns": "5.00",
                    "net_cogs": "495.00",
                    "net_profit": "1025.75",
                    "orders_paid_count": 42,
                    "average_ticket": "36.21",
                },
                "rows": [
                    {
                        "business_date": "2026-03-01",
                        "net_sales": "510.25",
                        "net_profit": "342.75",
                        "orders_paid_count": 15,
                    }
                ],
            }
        }
    )


DailyRow = ReportDailyRow
CalendarRow = ReportCalendarRow
ReportCalendarDay = ReportCalendarRow
