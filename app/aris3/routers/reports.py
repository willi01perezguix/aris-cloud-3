from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request

from app.aris3.core.deps import get_current_token_data, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import DEFAULT_BROAD_STORE_ROLES, enforce_store_scope
from app.aris3.db.session import get_db
from app.aris3.schemas.reports import (
    ReportCalendarDay,
    ReportCalendarResponse,
    ReportDailyResponse,
    ReportDailyRow,
    ReportMeta,
    ReportOverviewResponse,
    ReportTotals,
)
from app.aris3.services.reports import (
    daily_sales_refunds,
    iter_dates,
    resolve_date_range,
    resolve_timezone,
)


router = APIRouter()


def _resolve_store_id(token_data, store_id: str | None) -> str:
    if store_id:
        return store_id
    if token_data.store_id:
        return token_data.store_id
    raise AppError(ErrorCatalog.STORE_SCOPE_REQUIRED)


def _totals_from_days(
    rows: list[ReportDailyRow],
) -> ReportTotals:
    gross_sales = sum((row.gross_sales for row in rows), Decimal("0.00"))
    refunds_total = sum((row.refunds_total for row in rows), Decimal("0.00"))
    net_sales = sum((row.net_sales for row in rows), Decimal("0.00"))
    cogs_gross = sum((row.cogs_gross for row in rows), Decimal("0.00"))
    cogs_reversed = sum((row.cogs_reversed_from_returns for row in rows), Decimal("0.00"))
    net_cogs = sum((row.net_cogs for row in rows), Decimal("0.00"))
    net_profit = sum((row.net_profit for row in rows), Decimal("0.00"))
    orders_paid_count = sum((row.orders_paid_count for row in rows), 0)
    average_ticket = net_sales / Decimal(orders_paid_count) if orders_paid_count else Decimal("0.00")
    return ReportTotals(
        gross_sales=gross_sales,
        refunds_total=refunds_total,
        net_sales=net_sales,
        cogs_gross=cogs_gross,
        cogs_reversed_from_returns=cogs_reversed,
        net_cogs=net_cogs,
        net_profit=net_profit,
        orders_paid_count=orders_paid_count,
        average_ticket=average_ticket.quantize(Decimal("0.01")),
    )


def _build_daily_rows(
    sales_by_date: dict[date, Decimal],
    orders_by_date: dict[date, int],
    refunds_by_date: dict[date, Decimal],
    *,
    start_date: date,
    end_date: date,
) -> list[ReportDailyRow]:
    rows: list[ReportDailyRow] = []
    for day in iter_dates(start_date, end_date):
        gross_sales = sales_by_date.get(day, Decimal("0.00"))
        refunds_total = refunds_by_date.get(day, Decimal("0.00"))
        net_sales = gross_sales - refunds_total
        orders_paid_count = orders_by_date.get(day, 0)
        average_ticket = net_sales / Decimal(orders_paid_count) if orders_paid_count else Decimal("0.00")
        rows.append(
            ReportDailyRow(
                business_date=day,
                gross_sales=gross_sales,
                refunds_total=refunds_total,
                net_sales=net_sales,
                cogs_gross=Decimal("0.00"),
                cogs_reversed_from_returns=Decimal("0.00"),
                net_cogs=Decimal("0.00"),
                net_profit=net_sales,
                orders_paid_count=orders_paid_count,
                average_ticket=average_ticket.quantize(Decimal("0.01")),
            )
        )
    return rows


def _build_meta(request: Request, store_id: str, timezone_name: str, date_range, filters: dict, query_ms: float) -> ReportMeta:
    trace_id = getattr(request.state, "trace_id", None)
    return ReportMeta(
        store_id=store_id,
        timezone=timezone_name,
        from_datetime=date_range.start_local,
        to_datetime=date_range.end_local,
        trace_id=trace_id,
        query_ms=query_ms,
        filters=filters,
    )


@router.get("/aris3/reports/overview", response_model=ReportOverviewResponse)
def report_overview(
    request: Request,
    store_id: str | None = Query(None),
    from_value: str | None = Query(None, alias="from"),
    to_value: str | None = Query(None, alias="to"),
    timezone: str | None = Query(None),
    cashier: str | None = Query(None),
    channel: str | None = Query(None),
    payment_method: str | None = Query(None),
    token_data=Depends(get_current_token_data),
    _permission=Depends(require_permission("REPORTS_VIEW")),
    db=Depends(get_db),
):
    resolved_store_id = _resolve_store_id(token_data, store_id)
    store = enforce_store_scope(
        token_data,
        resolved_store_id,
        db,
        allow_superadmin=True,
        broader_store_roles=DEFAULT_BROAD_STORE_ROLES,
    )
    tz = resolve_timezone(timezone)
    date_range = resolve_date_range(from_value, to_value, tz)
    filters = {
        "store_id": resolved_store_id,
        "from": from_value,
        "to": to_value,
        "timezone": str(tz),
        "cashier": cashier,
        "channel": channel,
        "payment_method": payment_method,
    }
    start_time = time.perf_counter()
    sales_by_date, orders_by_date, refunds_by_date = daily_sales_refunds(
        db,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        tz=tz,
        cashier_id=cashier,
        payment_method=payment_method,
    )
    rows = _build_daily_rows(
        sales_by_date,
        orders_by_date,
        refunds_by_date,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
    )
    totals = _totals_from_days(rows)
    query_ms = (time.perf_counter() - start_time) * 1000
    meta = _build_meta(request, resolved_store_id, str(tz), date_range, filters, query_ms)
    return ReportOverviewResponse(meta=meta, totals=totals)


@router.get("/aris3/reports/daily", response_model=ReportDailyResponse)
def report_daily(
    request: Request,
    store_id: str | None = Query(None),
    from_value: str | None = Query(None, alias="from"),
    to_value: str | None = Query(None, alias="to"),
    timezone: str | None = Query(None),
    cashier: str | None = Query(None),
    channel: str | None = Query(None),
    payment_method: str | None = Query(None),
    token_data=Depends(get_current_token_data),
    _permission=Depends(require_permission("REPORTS_VIEW")),
    db=Depends(get_db),
):
    resolved_store_id = _resolve_store_id(token_data, store_id)
    store = enforce_store_scope(
        token_data,
        resolved_store_id,
        db,
        allow_superadmin=True,
        broader_store_roles=DEFAULT_BROAD_STORE_ROLES,
    )
    tz = resolve_timezone(timezone)
    date_range = resolve_date_range(from_value, to_value, tz)
    filters = {
        "store_id": resolved_store_id,
        "from": from_value,
        "to": to_value,
        "timezone": str(tz),
        "cashier": cashier,
        "channel": channel,
        "payment_method": payment_method,
    }
    start_time = time.perf_counter()
    sales_by_date, orders_by_date, refunds_by_date = daily_sales_refunds(
        db,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        tz=tz,
        cashier_id=cashier,
        payment_method=payment_method,
    )
    rows = _build_daily_rows(
        sales_by_date,
        orders_by_date,
        refunds_by_date,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
    )
    totals = _totals_from_days(rows)
    query_ms = (time.perf_counter() - start_time) * 1000
    meta = _build_meta(request, resolved_store_id, str(tz), date_range, filters, query_ms)
    return ReportDailyResponse(meta=meta, totals=totals, rows=rows)


@router.get("/aris3/reports/calendar", response_model=ReportCalendarResponse)
def report_calendar(
    request: Request,
    store_id: str | None = Query(None),
    from_value: str | None = Query(None, alias="from"),
    to_value: str | None = Query(None, alias="to"),
    timezone: str | None = Query(None),
    cashier: str | None = Query(None),
    channel: str | None = Query(None),
    payment_method: str | None = Query(None),
    token_data=Depends(get_current_token_data),
    _permission=Depends(require_permission("REPORTS_VIEW")),
    db=Depends(get_db),
):
    resolved_store_id = _resolve_store_id(token_data, store_id)
    store = enforce_store_scope(
        token_data,
        resolved_store_id,
        db,
        allow_superadmin=True,
        broader_store_roles=DEFAULT_BROAD_STORE_ROLES,
    )
    tz = resolve_timezone(timezone)
    date_range = resolve_date_range(from_value, to_value, tz)
    filters = {
        "store_id": resolved_store_id,
        "from": from_value,
        "to": to_value,
        "timezone": str(tz),
        "cashier": cashier,
        "channel": channel,
        "payment_method": payment_method,
    }
    start_time = time.perf_counter()
    sales_by_date, orders_by_date, refunds_by_date = daily_sales_refunds(
        db,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        tz=tz,
        cashier_id=cashier,
        payment_method=payment_method,
    )
    daily_rows = _build_daily_rows(
        sales_by_date,
        orders_by_date,
        refunds_by_date,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
    )
    calendar_rows = [
        ReportCalendarDay(
            business_date=row.business_date,
            net_sales=row.net_sales,
            net_profit=row.net_profit,
            orders_paid_count=row.orders_paid_count,
        )
        for row in daily_rows
    ]
    totals = _totals_from_days(daily_rows)
    query_ms = (time.perf_counter() - start_time) * 1000
    meta = _build_meta(request, resolved_store_id, str(tz), date_range, filters, query_ms)
    return ReportCalendarResponse(meta=meta, totals=totals, rows=calendar_rows)
