from __future__ import annotations

import logging
import time
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request

from app.aris3.core.deps import get_current_token_data, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import DEFAULT_BROAD_STORE_ROLES, enforce_store_scope
from app.aris3.core.config import settings
from app.aris3.db.session import get_db
from app.aris3.schemas.reports import (
    ReportCalendarDay,
    ReportCalendarResponse,
    ReportDailyResponse,
    ReportDailyRow,
    ReportFilters,
    ReportMeta,
    ReportOverviewResponse,
    ReportTotals,
)
from app.aris3.services.reports import (
    apply_liability_and_tender_rows,
    build_daily_report_rows,
    build_report_totals,
    daily_sales_refunds,
    eligible_sales_count_by_store,
    resolve_date_range,
    resolve_timezone,
    validate_date_range,
)


router = APIRouter()
logger = logging.getLogger(__name__)


def _resolve_store_id(token_data, store_id: str | None) -> str:
    if store_id:
        return store_id
    if token_data.store_id:
        return token_data.store_id
    raise AppError(ErrorCatalog.STORE_SCOPE_REQUIRED)


def _build_meta(
    request: Request,
    *,
    requested_store_id: str | None,
    resolved_store_id: str,
    token_store_id: str | None,
    timezone_name: str,
    date_range,
    filters: ReportFilters,
    query_ms: float,
    eligible_sales_count_by_store: dict[str, int],
) -> ReportMeta:
    trace_id = getattr(request.state, "trace_id", None)
    return ReportMeta(
        store_id=resolved_store_id,
        requested_store_id=requested_store_id,
        resolved_store_id=resolved_store_id,
        token_store_id=token_store_id,
        all_stores=False,
        timezone=timezone_name,
        from_datetime=date_range.start_local,
        to_datetime=date_range.end_local,
        from_datetime_utc=date_range.start_utc,
        to_datetime_utc=date_range.end_utc,
        eligible_sales_count_by_store=eligible_sales_count_by_store,
        trace_id=trace_id,
        query_ms=query_ms,
        filters=filters,
    )




@router.get(
    "/aris3/reports/overview",
    response_model=ReportOverviewResponse,
    responses={
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                }
            },
        }
    },
)
def report_overview(
    request: Request,
    store_id: str | None = Query(None),
    from_value: str | None = Query(None, alias="from", description="ISO 8601/date, inclusive start"),
    to_value: str | None = Query(None, alias="to", description="ISO 8601/date, inclusive end"),
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
    validate_date_range(date_range, max_days=settings.REPORTS_MAX_DATE_RANGE_DAYS)
    filters = ReportFilters(
        store_id=resolved_store_id,
        **{
            "from": date_range.start_local.isoformat(),
            "to": date_range.end_local.isoformat(),
        },
        timezone=str(tz),
        cashier=cashier,
        channel=channel,
        payment_method=payment_method,
    )
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
    rows_data = build_daily_report_rows(
        sales_by_date,
        orders_by_date,
        refunds_by_date,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
    )
    rows_data = apply_liability_and_tender_rows(
        db,
        rows_data=rows_data,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        tz=tz,
    )
    rows = [ReportDailyRow(**row) for row in rows_data]
    totals = ReportTotals(**build_report_totals(rows_data))
    sales_count_by_store = eligible_sales_count_by_store(
        db,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        cashier_id=cashier,
        payment_method=payment_method,
    )
    query_ms = (time.perf_counter() - start_time) * 1000
    meta = _build_meta(
        request,
        requested_store_id=store_id,
        resolved_store_id=resolved_store_id,
        token_store_id=token_data.store_id,
        timezone_name=str(tz),
        date_range=date_range,
        filters=filters,
        query_ms=query_ms,
        eligible_sales_count_by_store=sales_count_by_store,
    )
    logger.info(
        "reports_overview",
        extra={
            "trace_id": meta.trace_id,
            "tenant_id": str(store.tenant_id),
            "store_id": resolved_store_id,
            "endpoint": "/aris3/reports/overview",
            "latency_ms": query_ms,
            "row_count": len(rows),
            "requested_store_id": store_id,
            "resolved_store_id": resolved_store_id,
            "token_store_id": token_data.store_id,
            "all_stores": False,
            "from_utc": date_range.start_utc.isoformat(),
            "to_utc": date_range.end_utc.isoformat(),
            "eligible_sales_count_by_store": sales_count_by_store,
        },
    )
    return ReportOverviewResponse(meta=meta, totals=totals)


@router.get(
    "/aris3/reports/daily",
    response_model=ReportDailyResponse,
    responses={
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                }
            },
        }
    },
)
def report_daily(
    request: Request,
    store_id: str | None = Query(None),
    from_value: str | None = Query(None, alias="from", description="ISO 8601/date, inclusive start"),
    to_value: str | None = Query(None, alias="to", description="ISO 8601/date, inclusive end"),
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
    validate_date_range(date_range, max_days=settings.REPORTS_MAX_DATE_RANGE_DAYS)
    filters = ReportFilters(
        store_id=resolved_store_id,
        **{
            "from": date_range.start_local.isoformat(),
            "to": date_range.end_local.isoformat(),
        },
        timezone=str(tz),
        cashier=cashier,
        channel=channel,
        payment_method=payment_method,
    )
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
    rows_data = build_daily_report_rows(
        sales_by_date,
        orders_by_date,
        refunds_by_date,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
    )
    rows_data = apply_liability_and_tender_rows(
        db,
        rows_data=rows_data,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        tz=tz,
    )
    rows = [ReportDailyRow(**row) for row in rows_data]
    totals = ReportTotals(**build_report_totals(rows_data))
    sales_count_by_store = eligible_sales_count_by_store(
        db,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        cashier_id=cashier,
        payment_method=payment_method,
    )
    query_ms = (time.perf_counter() - start_time) * 1000
    meta = _build_meta(
        request,
        requested_store_id=store_id,
        resolved_store_id=resolved_store_id,
        token_store_id=token_data.store_id,
        timezone_name=str(tz),
        date_range=date_range,
        filters=filters,
        query_ms=query_ms,
        eligible_sales_count_by_store=sales_count_by_store,
    )
    logger.info(
        "reports_daily",
        extra={
            "trace_id": meta.trace_id,
            "tenant_id": str(store.tenant_id),
            "store_id": resolved_store_id,
            "endpoint": "/aris3/reports/daily",
            "latency_ms": query_ms,
            "row_count": len(rows),
            "requested_store_id": store_id,
            "resolved_store_id": resolved_store_id,
            "token_store_id": token_data.store_id,
            "all_stores": False,
            "from_utc": date_range.start_utc.isoformat(),
            "to_utc": date_range.end_utc.isoformat(),
            "eligible_sales_count_by_store": sales_count_by_store,
        },
    )
    return ReportDailyResponse(meta=meta, totals=totals, rows=rows)


@router.get(
    "/aris3/reports/calendar",
    response_model=ReportCalendarResponse,
    responses={
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                }
            },
        }
    },
)
def report_calendar(
    request: Request,
    store_id: str | None = Query(None),
    from_value: str | None = Query(None, alias="from", description="ISO 8601/date, inclusive start"),
    to_value: str | None = Query(None, alias="to", description="ISO 8601/date, inclusive end"),
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
    validate_date_range(date_range, max_days=settings.REPORTS_MAX_DATE_RANGE_DAYS)
    filters = ReportFilters(
        store_id=resolved_store_id,
        **{
            "from": date_range.start_local.isoformat(),
            "to": date_range.end_local.isoformat(),
        },
        timezone=str(tz),
        cashier=cashier,
        channel=channel,
        payment_method=payment_method,
    )
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
    daily_rows_data = build_daily_report_rows(
        sales_by_date,
        orders_by_date,
        refunds_by_date,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
    )
    daily_rows_data = apply_liability_and_tender_rows(
        db,
        rows_data=daily_rows_data,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        tz=tz,
    )
    daily_rows = [ReportDailyRow(**row) for row in daily_rows_data]
    calendar_rows = [
        ReportCalendarDay(
            business_date=row.business_date,
            net_sales=row.net_sales,
            net_profit=row.net_profit,
            orders_paid_count=row.orders_paid_count,
        )
        for row in daily_rows
    ]
    totals = ReportTotals(**build_report_totals(daily_rows_data))
    sales_count_by_store = eligible_sales_count_by_store(
        db,
        tenant_id=str(store.tenant_id),
        store_id=resolved_store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        cashier_id=cashier,
        payment_method=payment_method,
    )
    query_ms = (time.perf_counter() - start_time) * 1000
    meta = _build_meta(
        request,
        requested_store_id=store_id,
        resolved_store_id=resolved_store_id,
        token_store_id=token_data.store_id,
        timezone_name=str(tz),
        date_range=date_range,
        filters=filters,
        query_ms=query_ms,
        eligible_sales_count_by_store=sales_count_by_store,
    )
    logger.info(
        "reports_calendar",
        extra={
            "trace_id": meta.trace_id,
            "tenant_id": str(store.tenant_id),
            "store_id": resolved_store_id,
            "endpoint": "/aris3/reports/calendar",
            "latency_ms": query_ms,
            "row_count": len(calendar_rows),
            "requested_store_id": store_id,
            "resolved_store_id": resolved_store_id,
            "token_store_id": token_data.store_id,
            "all_stores": False,
            "from_utc": date_range.start_utc.isoformat(),
            "to_utc": date_range.end_utc.isoformat(),
            "eligible_sales_count_by_store": sales_count_by_store,
        },
    )
    return ReportCalendarResponse(meta=meta, totals=totals, rows=calendar_rows)
