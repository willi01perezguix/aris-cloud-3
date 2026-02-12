from __future__ import annotations

def _resolve_timezone(tz: str | None):
    # UTC aliases are always valid
    if not tz or tz in ("UTC", "Z", "Etc/UTC"):
        return dt_timezone.utc
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        # Windows fallback when system tzdata is missing
        try:
            from dateutil import tz as dateutil_tz  # type: ignore
            alt = dateutil_tz.gettz(tz)
            if alt is not None:
                return alt
        except Exception:
            pass
        raise

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from datetime import timezone as dt_timezone
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import Select, func, select

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import PosPayment, PosReturnEvent, PosSale, PosSaleLine


class ReportDateRange:
    def __init__(
        self,
        *,
        start_local: datetime,
        end_local: datetime,
        start_utc: datetime,
        end_utc: datetime,
        timezone_name: str,
    ) -> None:
        self.start_local = start_local
        self.end_local = end_local
        self.start_utc = start_utc
        self.end_utc = end_utc
        self.timezone_name = timezone_name

    @property
    def start_date(self) -> date:
        return self.start_local.date()

    @property
    def end_date(self) -> date:
        return self.end_local.date()


def resolve_timezone(timezone_name: str | None) -> ZoneInfo:
    tz_name = timezone_name or "UTC"
    try:
        return _resolve_timezone(tz_name)
    except Exception as exc:  # pragma: no cover - depends on system tzdata
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "invalid timezone"}) from exc


def resolve_date_range(from_value: str | None, to_value: str | None, tz: ZoneInfo) -> ReportDateRange:
    now_local = datetime.now(tz)
    start_local, _ = _parse_datetime_or_date(from_value, tz, default=now_local.replace(hour=0, minute=0, second=0, microsecond=0))
    end_local, to_is_date = _parse_datetime_or_date(to_value, tz, default=now_local)
    if to_is_date:
        end_local = end_local + timedelta(days=1) - timedelta(microseconds=1)
    if end_local < start_local:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "to must be after from"})
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return ReportDateRange(
        start_local=start_local,
        end_local=end_local,
        start_utc=start_utc,
        end_utc=end_utc,
        timezone_name=str(tz),
    )


def validate_date_range(date_range: ReportDateRange, *, max_days: int) -> None:
    if max_days <= 0:
        return
    days = (date_range.end_date - date_range.start_date).days + 1
    if days > max_days:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={
                "message": "date range exceeds limit",
                "reason_code": "REPORT_DATE_RANGE_LIMIT_EXCEEDED",
                "max_days": max_days,
            },
        )


def _parse_datetime_or_date(value: str | None, tz: ZoneInfo, *, default: datetime) -> tuple[datetime, bool]:
    if not value:
        return default, False
    normalized = value.replace("Z", "+00:00")
    if "T" in normalized or ":" in normalized:
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "invalid datetime"}) from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=tz), False
        return parsed.astimezone(tz), False
    try:
        parsed_date = date.fromisoformat(normalized)
    except ValueError as exc:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "invalid date"}) from exc
    return datetime.combine(parsed_date, time.min, tzinfo=tz), True


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def paid_sales_query(
    *,
    tenant_id: str,
    store_id: str,
    start_utc: datetime,
    end_utc: datetime,
    cashier_id: str | None,
    payment_method: str | None,
) -> Select:
    query = select(PosSale.id, PosSale.checked_out_at).where(
        PosSale.tenant_id == tenant_id,
        PosSale.store_id == store_id,
        PosSale.status == "PAID",
        PosSale.checked_out_at.is_not(None),
        PosSale.checked_out_at >= start_utc,
        PosSale.checked_out_at <= end_utc,
    )
    if cashier_id:
        query = query.where(PosSale.checked_out_by_user_id == cashier_id)
    if payment_method:
        payment_subquery = (
            select(PosPayment.sale_id)
            .where(
                PosPayment.tenant_id == tenant_id,
                PosPayment.method == payment_method,
            )
            .distinct()
        )
        query = query.where(PosSale.id.in_(payment_subquery))
    return query


def refund_events_query(
    *,
    tenant_id: str,
    store_id: str,
    start_utc: datetime,
    end_utc: datetime,
    cashier_id: str | None,
) -> Select:
    query = select(PosReturnEvent.refund_total, PosReturnEvent.created_at).where(
        PosReturnEvent.tenant_id == tenant_id,
        PosReturnEvent.store_id == store_id,
        PosReturnEvent.created_at >= start_utc,
        PosReturnEvent.created_at <= end_utc,
    )
    if cashier_id:
        query = query.join(PosSale, PosSale.id == PosReturnEvent.sale_id).where(
            PosSale.checked_out_by_user_id == cashier_id
        )
    return query


def sale_line_totals(
    db,
    *,
    sale_ids: list[str],
) -> dict[str, Decimal]:
    if not sale_ids:
        return {}
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    rows = db.execute(
        select(PosSaleLine.sale_id, func.sum(PosSaleLine.line_total))
        .where(PosSaleLine.sale_id.in_(sale_ids))
        .group_by(PosSaleLine.sale_id)
    ).all()
    for sale_id, line_total in rows:
        totals[str(sale_id)] += Decimal(str(line_total or 0.0))
    return totals


def daily_sales_refunds(
    db,
    *,
    tenant_id: str,
    store_id: str,
    start_utc: datetime,
    end_utc: datetime,
    tz: ZoneInfo,
    cashier_id: str | None = None,
    payment_method: str | None = None,
) -> tuple[dict[date, Decimal], dict[date, int], dict[date, Decimal]]:
    sale_rows = db.execute(
        paid_sales_query(
            tenant_id=tenant_id,
            store_id=store_id,
            start_utc=start_utc,
            end_utc=end_utc,
            cashier_id=cashier_id,
            payment_method=payment_method,
        )
    ).all()
    sale_ids = [str(row.id) for row in sale_rows]
    sale_totals = sale_line_totals(db, sale_ids=sale_ids)
    sales_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    orders_by_date: dict[date, int] = defaultdict(int)
    for row in sale_rows:
        checked_out_at = _ensure_utc(row.checked_out_at)
        local_date = checked_out_at.astimezone(tz).date()
        orders_by_date[local_date] += 1
        sales_by_date[local_date] += sale_totals.get(str(row.id), Decimal("0.00"))

    refund_rows = db.execute(
        refund_events_query(
            tenant_id=tenant_id,
            store_id=store_id,
            start_utc=start_utc,
            end_utc=end_utc,
            cashier_id=cashier_id,
        )
    ).all()
    refunds_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for refund_total, created_at in refund_rows:
        local_date = _ensure_utc(created_at).astimezone(tz).date()
        refunds_by_date[local_date] += Decimal(str(refund_total or 0.0))

    return sales_by_date, orders_by_date, refunds_by_date

