from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from datetime import timezone as dt_timezone
from decimal import Decimal
import logging
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import Select, func, select

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import PosAdvance, PosAdvanceEvent, PosPayment, PosReturnEvent, PosSale, PosSaleLine, StockItem
from app.aris3.services.sale_statuses import FINALIZED_SALE_STATUSES


logger = logging.getLogger(__name__)


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
        func.upper(PosSale.status).in_(FINALIZED_SALE_STATUSES),
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
    cogs_gross_by_date: dict[date, Decimal] | None = None,
    cogs_reversed_by_date: dict[date, Decimal] | None = None,
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Decimal | date | int]]:
    rows: list[dict[str, Decimal | date | int]] = []
    for day in iter_dates(start_date, end_date):
        gross_sales = sales_by_date.get(day, Decimal("0.00"))
        refunds_total = refunds_by_date.get(day, Decimal("0.00"))
        cogs_gross = (cogs_gross_by_date or {}).get(day, Decimal("0.00"))
        cogs_reversed = (cogs_reversed_by_date or {}).get(day, Decimal("0.00"))
        net_cogs = cogs_gross - cogs_reversed
        net_sales = gross_sales - refunds_total
        orders_paid_count = orders_by_date.get(day, 0)
        average_ticket = net_sales / Decimal(orders_paid_count) if orders_paid_count else Decimal("0.00")
        rows.append(
            {
                "business_date": day,
                "gross_sales": gross_sales,
                "refunds_total": refunds_total,
                "net_sales": net_sales,
                "cogs_gross": cogs_gross,
                "cogs_reversed_from_returns": cogs_reversed,
                "net_cogs": net_cogs,
                "net_profit": net_sales - net_cogs,
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
            func.upper(PosSale.status).in_(FINALIZED_SALE_STATUSES),
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


def sale_line_costs_and_diagnostics(
    db,
    *,
    tenant_id: str,
    store_id: str,
    sale_ids: list[str],
) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, int | dict[str, int]]]:
    if not sale_ids:
        return {}, {}, {"missing_cost_lines": 0, "missing_cost_total_qty": 0, "cost_source_summary": {}}

    sale_line_rows = db.execute(
        select(
            PosSaleLine.id,
            PosSaleLine.sale_id,
            PosSaleLine.qty,
            PosSaleLine.line_total,
            PosSaleLine.cost_price_snapshot,
            PosSaleLine.item_uid,
            PosSaleLine.epc_at_sale,
            PosSaleLine.epc,
            PosSaleLine.sku_snapshot,
            PosSaleLine.sku,
            PosSaleLine.var1_snapshot,
            PosSaleLine.var1_value,
            PosSaleLine.var2_snapshot,
            PosSaleLine.var2_value,
        ).where(
            PosSaleLine.tenant_id == tenant_id,
            PosSaleLine.sale_id.in_(sale_ids),
        )
    ).all()

    item_uids = {row.item_uid for row in sale_line_rows if row.item_uid}
    epcs = {row.epc_at_sale or row.epc for row in sale_line_rows if (row.epc_at_sale or row.epc)}
    sku_keys = {
        (
            row.sku_snapshot or row.sku,
            row.var1_snapshot or row.var1_value,
            row.var2_snapshot or row.var2_value,
        )
        for row in sale_line_rows
        if (row.sku_snapshot or row.sku)
    }

    stock_by_item_uid: dict[object, Decimal | None] = {}
    if item_uids:
        for item_uid, cost_price in db.execute(
            select(StockItem.item_uid, StockItem.cost_price).where(
                StockItem.tenant_id == tenant_id,
                StockItem.store_id == store_id,
                StockItem.item_uid.in_(item_uids),
            )
        ).all():
            stock_by_item_uid[item_uid] = Decimal(str(cost_price)) if cost_price is not None else None

    stock_by_epc: dict[str, Decimal | None] = {}
    if epcs:
        epc_rows = db.execute(
            select(StockItem.epc, StockItem.cost_price).where(
                StockItem.tenant_id == tenant_id,
                StockItem.store_id == store_id,
                StockItem.epc.in_(list(epcs)),
            )
        ).all()
        epc_map: dict[str, list[Decimal | None]] = defaultdict(list)
        for epc, cost_price in epc_rows:
            if epc:
                epc_map[epc].append(Decimal(str(cost_price)) if cost_price is not None else None)
        for epc, matches in epc_map.items():
            if len(matches) == 1:
                stock_by_epc[epc] = matches[0]

    stock_by_sku_variant: dict[tuple[str, str | None, str | None], Decimal | None] = {}
    if sku_keys:
        sku_values = {key[0] for key in sku_keys if key[0]}
        sku_rows = db.execute(
            select(StockItem.sku, StockItem.var1_value, StockItem.var2_value, StockItem.cost_price).where(
                StockItem.tenant_id == tenant_id,
                StockItem.store_id == store_id,
                StockItem.sku.in_(list(sku_values)),
            )
        ).all()
        sku_map: dict[tuple[str, str | None, str | None], list[Decimal | None]] = defaultdict(list)
        for sku, var1, var2, cost_price in sku_rows:
            if not sku:
                continue
            sku_map[(sku, var1, var2)].append(Decimal(str(cost_price)) if cost_price is not None else None)
        for key, matches in sku_map.items():
            if len(matches) == 1:
                stock_by_sku_variant[key] = matches[0]

    cost_by_line_id: dict[str, Decimal] = {}
    qty_by_line_id: dict[str, int] = {}
    revenue_by_line_id: dict[str, Decimal] = {}
    cogs_gross_by_sale: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    cost_source_summary: dict[str, int] = defaultdict(int)
    missing_cost_lines = 0
    missing_cost_total_qty = 0

    for row in sale_line_rows:
        line_id = str(row.id)
        qty = int(row.qty or 0)
        qty_by_line_id[line_id] = qty
        revenue_by_line_id[line_id] = Decimal(str(row.line_total or 0.0))
        unit_cost: Decimal | None = None
        cost_source = "missing"

        if row.cost_price_snapshot is not None:
            unit_cost = Decimal(str(row.cost_price_snapshot))
            cost_source = "snapshot"
        elif row.item_uid and row.item_uid in stock_by_item_uid:
            unit_cost = stock_by_item_uid[row.item_uid]
            cost_source = "fallback_item_uid"
        elif (row.epc_at_sale or row.epc) and (row.epc_at_sale or row.epc) in stock_by_epc:
            unit_cost = stock_by_epc[row.epc_at_sale or row.epc]
            cost_source = "fallback_epc"
        else:
            sku_key = (
                row.sku_snapshot or row.sku,
                row.var1_snapshot or row.var1_value,
                row.var2_snapshot or row.var2_value,
            )
            if sku_key in stock_by_sku_variant:
                unit_cost = stock_by_sku_variant[sku_key]
                cost_source = "fallback_sku_variant"

        if unit_cost is None:
            missing_cost_lines += 1
            missing_cost_total_qty += max(qty, 0)
            unit_cost = Decimal("0.00")

        line_cost = (unit_cost * Decimal(qty)).quantize(Decimal("0.01"))
        cost_by_line_id[line_id] = line_cost
        cogs_gross_by_sale[str(row.sale_id)] += line_cost
        cost_source_summary[cost_source] += 1

    diagnostics = {
        "missing_cost_lines": missing_cost_lines,
        "missing_cost_total_qty": missing_cost_total_qty,
        "cost_source_summary": dict(cost_source_summary),
    }
    return cogs_gross_by_sale, revenue_by_line_id, {**diagnostics, "cost_by_line_id": cost_by_line_id, "qty_by_line_id": qty_by_line_id}


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
) -> tuple[dict[date, Decimal], dict[date, int], dict[date, Decimal], dict[date, Decimal], dict[date, Decimal], dict[str, int | dict[str, int]]]:
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
    cogs_by_sale, _revenue_by_line_id, cost_diag = sale_line_costs_and_diagnostics(
        db,
        tenant_id=tenant_id,
        store_id=store_id,
        sale_ids=sale_ids,
    )
    sales_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    orders_by_date: dict[date, int] = defaultdict(int)
    cogs_gross_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in sale_rows:
        checked_out_at = _ensure_utc(row.checked_out_at)
        local_date = checked_out_at.astimezone(tz).date()
        orders_by_date[local_date] += 1
        line_total = sale_totals.get(str(row.id))
        if line_total is None:
            line_total = Decimal(str(row.total_due or 0.0))
        sales_by_date[local_date] += line_total
        cogs_gross_by_date[local_date] += cogs_by_sale.get(str(row.id), Decimal("0.00"))

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

    cogs_reversed_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    return_events = db.execute(
        select(PosReturnEvent.created_at, PosReturnEvent.payload)
        .where(
            PosReturnEvent.tenant_id == tenant_id,
            PosReturnEvent.store_id == store_id,
            PosReturnEvent.action.in_(REPORTABLE_RETURN_ACTIONS),
            PosReturnEvent.created_at >= start_utc,
            PosReturnEvent.created_at <= end_utc,
        )
    ).all()
    cost_by_line_id = cost_diag.get("cost_by_line_id", {})
    qty_by_line_id = cost_diag.get("qty_by_line_id", {})
    for created_at, payload in return_events:
        local_date = _ensure_utc(created_at).astimezone(tz).date()
        event_payload = payload or {}
        for item in event_payload.get("returned_lines", []) or []:
            line_id = str(item.get("line_id") or item.get("sale_line_id") or "")
            qty = int(item.get("qty") or 0)
            if not line_id or qty <= 0:
                continue
            line_cost = Decimal(str(cost_by_line_id.get(line_id, Decimal("0.00"))))
            if line_cost <= 0:
                continue
            sold_qty = max(int(qty_by_line_id.get(line_id, 0)), 1)
            unit_cost = (line_cost / Decimal(sold_qty)).quantize(Decimal("0.01"))
            cogs_reversed_by_date[local_date] += (unit_cost * Decimal(qty)).quantize(Decimal("0.01"))

    cost_diag.pop("cost_by_line_id", None)
    cost_diag.pop("qty_by_line_id", None)
    return sales_by_date, orders_by_date, refunds_by_date, cogs_gross_by_date, cogs_reversed_by_date, cost_diag


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
