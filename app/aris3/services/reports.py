from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from datetime import timezone as dt_timezone
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import Select, func, select

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import PosAdvance, PosAdvanceEvent, PosPayment, PosReturnEvent, PosSale, PosSaleLine


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


UTC_ALIASES = {"UTC", "Z", "Etc/UTC"}
REPORTABLE_RETURN_ACTIONS = ("REFUND_ITEMS", "EXCHANGE_ITEMS")
REPORTABLE_SALE_STATUSES = ("PAID", "COMPLETED", "CLOSED", "FINALIZED")
_MONETARY_DEFAULT = Decimal("0.00")
_LIABILITY_TENDER_FIELDS = (
    "liability_issued_advances",
    "liability_issued_gift_cards",
    "liability_redeemed_advances",
    "liability_redeemed_gift_cards",
    "liability_refunded_advances",
    "liability_refunded_gift_cards",
    "tender_cash_received",
    "tender_card_received",
    "tender_transfer_received",
    "tender_total_received",
)


def _normalize_timezone_name(timezone_name: str | None) -> str:
    tz_name = (timezone_name or "UTC").strip()
    return "UTC" if tz_name in UTC_ALIASES else tz_name


def resolve_timezone(timezone_name: str | None):
    tz_name = _normalize_timezone_name(timezone_name)
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:  # pragma: no cover - depends on system tzdata
        if tz_name == "UTC":
            return dt_timezone.utc
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"errors": [{"field": "timezone", "message": "invalid timezone", "type": "value_error.timezone"}]}) from exc


def resolve_date_range(from_value: str | None, to_value: str | None, tz: ZoneInfo) -> ReportDateRange:
    now_local = datetime.now(tz)
    start_local, from_is_date = _parse_datetime_or_date(
        from_value,
        tz,
        field_name="from",
        default=now_local.replace(hour=0, minute=0, second=0, microsecond=0),
    )
    if from_is_date:
        start_local = start_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local, to_is_date = _parse_datetime_or_date(to_value, tz, field_name="to", default=now_local)
    if to_is_date:
        end_local = end_local + timedelta(days=1) - timedelta(microseconds=1)
    if end_local < start_local:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"errors": [{"field": "to", "message": "to must be greater than or equal to from", "type": "value_error.date_range"}]})
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
                "errors": [
                    {
                        "field": "to",
                        "message": "date range exceeds limit",
                        "type": "value_error.date_range_limit",
                    }
                ],
                "reason_code": "REPORT_DATE_RANGE_LIMIT_EXCEEDED",
                "max_days": max_days,
            },
        )


def _parse_datetime_or_date(value: str | None, tz: ZoneInfo, *, field_name: str, default: datetime) -> tuple[datetime, bool]:
    if not value:
        return default, False
    normalized = value.replace("Z", "+00:00")
    if "T" in normalized or ":" in normalized:
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"errors": [{"field": field_name, "message": "invalid datetime", "type": "value_error.datetime"}]},
            ) from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=tz), False
        return parsed.astimezone(tz), False
    try:
        parsed_date = date.fromisoformat(normalized)
    except ValueError as exc:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"errors": [{"field": field_name, "message": "invalid date", "type": "value_error.date"}]},
        ) from exc
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
    query = select(PosSale.id, PosSale.checked_out_at, PosSale.total_due).where(
        PosSale.tenant_id == tenant_id,
        PosSale.store_id == store_id,
        func.upper(PosSale.status).in_(REPORTABLE_SALE_STATUSES),
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
    payment_method: str | None,
) -> Select:
    query = select(PosReturnEvent.refund_total, PosReturnEvent.created_at).where(
        PosReturnEvent.tenant_id == tenant_id,
        PosReturnEvent.store_id == store_id,
        PosReturnEvent.action.in_(REPORTABLE_RETURN_ACTIONS),
        PosReturnEvent.created_at >= start_utc,
        PosReturnEvent.created_at <= end_utc,
    )
    if cashier_id or payment_method:
        query = query.join(PosSale, PosSale.id == PosReturnEvent.sale_id).where(
            PosSale.tenant_id == tenant_id,
            PosSale.store_id == store_id,
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
        query = query.where(PosReturnEvent.sale_id.in_(payment_subquery))
    return query


def build_daily_report_rows(
    sales_by_date: dict[date, Decimal],
    orders_by_date: dict[date, int],
    refunds_by_date: dict[date, Decimal],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Decimal | date | int]]:
    rows: list[dict[str, Decimal | date | int]] = []
    for day in iter_dates(start_date, end_date):
        gross_sales = sales_by_date.get(day, Decimal("0.00"))
        refunds_total = refunds_by_date.get(day, Decimal("0.00"))
        net_sales = gross_sales - refunds_total
        orders_paid_count = orders_by_date.get(day, 0)
        average_ticket = net_sales / Decimal(orders_paid_count) if orders_paid_count else Decimal("0.00")
        rows.append(
            {
                "business_date": day,
                "gross_sales": gross_sales,
                "refunds_total": refunds_total,
                "net_sales": net_sales,
                "cogs_gross": Decimal("0.00"),
                "cogs_reversed_from_returns": Decimal("0.00"),
                "net_cogs": Decimal("0.00"),
                "net_profit": net_sales,
                "orders_paid_count": orders_paid_count,
                "average_ticket": average_ticket.quantize(Decimal("0.01")),
                "liability_issued_advances": _MONETARY_DEFAULT,
                "liability_issued_gift_cards": _MONETARY_DEFAULT,
                "liability_redeemed_advances": _MONETARY_DEFAULT,
                "liability_redeemed_gift_cards": _MONETARY_DEFAULT,
                "liability_refunded_advances": _MONETARY_DEFAULT,
                "liability_refunded_gift_cards": _MONETARY_DEFAULT,
                "tender_cash_received": _MONETARY_DEFAULT,
                "tender_card_received": _MONETARY_DEFAULT,
                "tender_transfer_received": _MONETARY_DEFAULT,
                "tender_total_received": _MONETARY_DEFAULT,
            }
        )
    return rows


def _daily_liability_and_tender(
    db,
    *,
    tenant_id: str,
    store_id: str,
    start_utc: datetime,
    end_utc: datetime,
    tz: ZoneInfo,
) -> dict[date, dict[str, Decimal]]:
    rows: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: Decimal("0.00"))
    )

    issued = db.execute(
        select(PosAdvance.issued_at, PosAdvance.voucher_type, PosAdvance.issued_amount, PosAdvance.issued_payment_method)
        .where(
            PosAdvance.tenant_id == tenant_id,
            PosAdvance.store_id == store_id,
            PosAdvance.issued_at >= start_utc,
            PosAdvance.issued_at <= end_utc,
        )
    ).all()
    for issued_at, voucher_type, amount, payment_method in issued:
        day = _ensure_utc(issued_at).astimezone(tz).date()
        kind = (voucher_type or "ADVANCE").upper()
        method = (payment_method or "").upper()
        numeric = Decimal(str(amount or 0))
        if kind == "GIFT_CARD":
            rows[day]["liability_issued_gift_cards"] += numeric
        else:
            rows[day]["liability_issued_advances"] += numeric
        if method == "CASH":
            rows[day]["tender_cash_received"] += numeric
        elif method == "CARD":
            rows[day]["tender_card_received"] += numeric
        elif method == "TRANSFER":
            rows[day]["tender_transfer_received"] += numeric

    redeemed = db.execute(
        select(PosAdvanceEvent.created_at, PosAdvance.voucher_type, PosAdvance.issued_amount)
        .join(PosAdvance, PosAdvance.id == PosAdvanceEvent.advance_id)
        .where(
            PosAdvanceEvent.tenant_id == tenant_id,
            PosAdvanceEvent.store_id == store_id,
            PosAdvanceEvent.action == "CONSUMED",
            PosAdvanceEvent.created_at >= start_utc,
            PosAdvanceEvent.created_at <= end_utc,
        )
    ).all()
    for created_at, voucher_type, amount in redeemed:
        day = _ensure_utc(created_at).astimezone(tz).date()
        numeric = Decimal(str(amount or 0))
        if (voucher_type or "ADVANCE").upper() == "GIFT_CARD":
            rows[day]["liability_redeemed_gift_cards"] += numeric
        else:
            rows[day]["liability_redeemed_advances"] += numeric

    refunded = db.execute(
        select(PosAdvance.refunded_at, PosAdvance.voucher_type, PosAdvance.issued_amount)
        .where(
            PosAdvance.tenant_id == tenant_id,
            PosAdvance.store_id == store_id,
            PosAdvance.status == "REFUNDED",
            PosAdvance.refunded_at.is_not(None),
            PosAdvance.refunded_at >= start_utc,
            PosAdvance.refunded_at <= end_utc,
        )
    ).all()
    for refunded_at, voucher_type, amount in refunded:
        day = _ensure_utc(refunded_at).astimezone(tz).date()
        numeric = Decimal(str(amount or 0))
        if (voucher_type or "ADVANCE").upper() == "GIFT_CARD":
            rows[day]["liability_refunded_gift_cards"] += numeric
        else:
            rows[day]["liability_refunded_advances"] += numeric

    sales_tenders = db.execute(
        select(PosSale.checked_out_at, PosPayment.method, PosPayment.amount)
        .join(PosSale, PosSale.id == PosPayment.sale_id)
        .where(
            PosSale.tenant_id == tenant_id,
            PosSale.store_id == store_id,
            func.upper(PosSale.status).in_(REPORTABLE_SALE_STATUSES),
            PosSale.checked_out_at.is_not(None),
            PosSale.checked_out_at >= start_utc,
            PosSale.checked_out_at <= end_utc,
        )
    ).all()
    for checked_out_at, method, amount in sales_tenders:
        day = _ensure_utc(checked_out_at).astimezone(tz).date()
        numeric = Decimal(str(amount or 0))
        method = (method or "").upper()
        if method == "CASH":
            rows[day]["tender_cash_received"] += numeric
        elif method == "CARD":
            rows[day]["tender_card_received"] += numeric
        elif method == "TRANSFER":
            rows[day]["tender_transfer_received"] += numeric

    for values in rows.values():
        values["tender_total_received"] = (
            values["tender_cash_received"] + values["tender_card_received"] + values["tender_transfer_received"]
        )
    return rows


def build_report_totals(rows: list[dict[str, Decimal | date | int]]) -> dict[str, Decimal | int]:
    gross_sales = sum((Decimal(str(row.get("gross_sales", _MONETARY_DEFAULT))) for row in rows), _MONETARY_DEFAULT)
    refunds_total = sum((Decimal(str(row.get("refunds_total", _MONETARY_DEFAULT))) for row in rows), _MONETARY_DEFAULT)
    net_sales = sum((Decimal(str(row.get("net_sales", _MONETARY_DEFAULT))) for row in rows), _MONETARY_DEFAULT)
    cogs_gross = sum((Decimal(str(row.get("cogs_gross", _MONETARY_DEFAULT))) for row in rows), _MONETARY_DEFAULT)
    cogs_reversed = sum((Decimal(str(row.get("cogs_reversed_from_returns", _MONETARY_DEFAULT))) for row in rows), _MONETARY_DEFAULT)
    net_cogs = sum((Decimal(str(row.get("net_cogs", _MONETARY_DEFAULT))) for row in rows), _MONETARY_DEFAULT)
    net_profit = sum((Decimal(str(row.get("net_profit", _MONETARY_DEFAULT))) for row in rows), _MONETARY_DEFAULT)
    orders_paid_count = sum((int(row.get("orders_paid_count", 0)) for row in rows), 0)
    average_ticket = net_sales / Decimal(orders_paid_count) if orders_paid_count else Decimal("0.00")
    safe_rows: list[dict[str, Decimal | date | int]] = []
    for row in rows:
        normalized = dict(row)
        for field in _LIABILITY_TENDER_FIELDS:
            normalized[field] = Decimal(str(normalized.get(field, _MONETARY_DEFAULT)))
        safe_rows.append(normalized)

    liability_issued_advances = sum((row["liability_issued_advances"] for row in safe_rows), _MONETARY_DEFAULT)
    liability_issued_gift_cards = sum((row["liability_issued_gift_cards"] for row in safe_rows), _MONETARY_DEFAULT)
    liability_redeemed_advances = sum((row["liability_redeemed_advances"] for row in safe_rows), _MONETARY_DEFAULT)
    liability_redeemed_gift_cards = sum((row["liability_redeemed_gift_cards"] for row in safe_rows), _MONETARY_DEFAULT)
    liability_refunded_advances = sum((row["liability_refunded_advances"] for row in safe_rows), _MONETARY_DEFAULT)
    liability_refunded_gift_cards = sum((row["liability_refunded_gift_cards"] for row in safe_rows), _MONETARY_DEFAULT)
    tender_cash_received = sum((row["tender_cash_received"] for row in safe_rows), _MONETARY_DEFAULT)
    tender_card_received = sum((row["tender_card_received"] for row in safe_rows), _MONETARY_DEFAULT)
    tender_transfer_received = sum((row["tender_transfer_received"] for row in safe_rows), _MONETARY_DEFAULT)
    return {
        "gross_sales": gross_sales,
        "refunds_total": refunds_total,
        "net_sales": net_sales,
        "cogs_gross": cogs_gross,
        "cogs_reversed_from_returns": cogs_reversed,
        "net_cogs": net_cogs,
        "net_profit": net_profit,
        "orders_paid_count": orders_paid_count,
        "average_ticket": average_ticket.quantize(Decimal("0.01")),
        "liability_issued_advances": liability_issued_advances,
        "liability_issued_gift_cards": liability_issued_gift_cards,
        "liability_redeemed_advances": liability_redeemed_advances,
        "liability_redeemed_gift_cards": liability_redeemed_gift_cards,
        "liability_refunded_advances": liability_refunded_advances,
        "liability_refunded_gift_cards": liability_refunded_gift_cards,
        "tender_cash_received": tender_cash_received,
        "tender_card_received": tender_card_received,
        "tender_transfer_received": tender_transfer_received,
        "tender_total_received": tender_cash_received + tender_card_received + tender_transfer_received,
    }


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
        line_total = sale_totals.get(str(row.id))
        if line_total is None:
            line_total = Decimal(str(row.total_due or 0.0))
        sales_by_date[local_date] += line_total

    refund_rows = db.execute(
        refund_events_query(
            tenant_id=tenant_id,
            store_id=store_id,
            start_utc=start_utc,
            end_utc=end_utc,
            cashier_id=cashier_id,
            payment_method=payment_method,
        )
    ).all()
    refunds_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for refund_total, created_at in refund_rows:
        local_date = _ensure_utc(created_at).astimezone(tz).date()
        refunds_by_date[local_date] += Decimal(str(refund_total or 0.0))

    return sales_by_date, orders_by_date, refunds_by_date


def eligible_sales_count_by_store(
    db,
    *,
    tenant_id: str,
    store_id: str,
    start_utc: datetime,
    end_utc: datetime,
    cashier_id: str | None = None,
    payment_method: str | None = None,
) -> dict[str, int]:
    count_query = select(func.count()).select_from(
        paid_sales_query(
            tenant_id=tenant_id,
            store_id=store_id,
            start_utc=start_utc,
            end_utc=end_utc,
            cashier_id=cashier_id,
            payment_method=payment_method,
        ).subquery()
    )
    count = int(db.execute(count_query).scalar_one() or 0)
    return {store_id: count}


def apply_liability_and_tender_rows(
    db,
    *,
    rows_data: list[dict[str, Decimal | date | int]],
    tenant_id: str,
    store_id: str,
    start_utc: datetime,
    end_utc: datetime,
    tz: ZoneInfo,
) -> list[dict[str, Decimal | date | int]]:
    by_day = _daily_liability_and_tender(
        db,
        tenant_id=tenant_id,
        store_id=store_id,
        start_utc=start_utc,
        end_utc=end_utc,
        tz=tz,
    )
    for row in rows_data:
        day = row["business_date"]
        extras = by_day.get(day, {})
        row["liability_issued_advances"] = extras.get("liability_issued_advances", Decimal("0.00"))
        row["liability_issued_gift_cards"] = extras.get("liability_issued_gift_cards", Decimal("0.00"))
        row["liability_redeemed_advances"] = extras.get("liability_redeemed_advances", Decimal("0.00"))
        row["liability_redeemed_gift_cards"] = extras.get("liability_redeemed_gift_cards", Decimal("0.00"))
        row["liability_refunded_advances"] = extras.get("liability_refunded_advances", Decimal("0.00"))
        row["liability_refunded_gift_cards"] = extras.get("liability_refunded_gift_cards", Decimal("0.00"))
        row["tender_cash_received"] = extras.get("tender_cash_received", Decimal("0.00"))
        row["tender_card_received"] = extras.get("tender_card_received", Decimal("0.00"))
        row["tender_transfer_received"] = extras.get("tender_transfer_received", Decimal("0.00"))
        row["tender_total_received"] = extras.get("tender_total_received", Decimal("0.00"))
    return rows_data
