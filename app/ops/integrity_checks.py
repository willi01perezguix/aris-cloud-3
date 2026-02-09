from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from decimal import Decimal

from sqlalchemy import func, select

from app.aris3.core.metrics import metrics
from app.aris3.db.models import (
    PosCashSession,
    PosSale,
    PosSaleLine,
    StockItem,
    Tenant,
    Transfer,
)


SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_WARN = "WARN"
VENDIBLE_LOCATION_CODES = {"BODEGA", "STORE"}


@dataclass(frozen=True)
class IntegrityFinding:
    check_id: str
    severity: str
    tenant_id: str
    message: str
    entity: str
    entity_id: str | None
    details: dict


def _normalize_epc(epc: str | None) -> str | None:
    if not epc:
        return None
    cleaned = re.sub(r"[^0-9a-fA-F]", "", epc).upper()
    if len(cleaned) != 24:
        return None
    return cleaned


def resolve_tenants(db, tenant: str) -> list[str]:
    if tenant.lower() != "all":
        return [tenant]
    return [str(row.id) for row in db.execute(select(Tenant.id)).all()]


def check_total_vendible_status(db, tenant_id: str) -> list[IntegrityFinding]:
    rows = db.execute(
        select(StockItem.id, StockItem.status, StockItem.location_code)
        .where(StockItem.tenant_id == tenant_id)
        .where(StockItem.location_is_vendible.is_(True))
        .where(StockItem.location_code.in_(VENDIBLE_LOCATION_CODES))
        .where(StockItem.status.notin_({"RFID", "PENDING"}))
    ).all()
    findings = []
    for row in rows:
        findings.append(
            IntegrityFinding(
                check_id="total_equals_rfid_pending",
                severity=SEVERITY_CRITICAL,
                tenant_id=tenant_id,
                message="Vendible stock has status outside RFID/PENDING.",
                entity="stock_items",
                entity_id=str(row.id),
                details={"status": row.status, "location_code": row.location_code},
            )
        )
    if rows:
        metrics.increment_invariant_violation("total_equals_rfid_pending", len(rows))
    return findings


def check_duplicate_epc(db, tenant_id: str) -> list[IntegrityFinding]:
    rows = db.execute(
        select(StockItem.id, StockItem.epc).where(StockItem.tenant_id == tenant_id).where(StockItem.epc.is_not(None))
    ).all()
    index: dict[str, list[str]] = {}
    for row in rows:
        normalized = _normalize_epc(row.epc)
        if not normalized:
            continue
        index.setdefault(normalized, []).append(str(row.id))
    findings = []
    for normalized, ids in index.items():
        if len(ids) > 1:
            findings.append(
                IntegrityFinding(
                    check_id="duplicate_epc",
                    severity=SEVERITY_CRITICAL,
                    tenant_id=tenant_id,
                    message="Duplicate EPC detected for tenant.",
                    entity="stock_items",
                    entity_id=None,
                    details={"epc": normalized, "stock_item_ids": ids},
                )
            )
    if findings:
        metrics.increment_invariant_violation("duplicate_epc", len(findings))
    return findings


def check_non_reusable_label_reuse(db, tenant_id: str) -> list[IntegrityFinding]:
    sale_lines = db.execute(
        select(PosSaleLine.epc)
        .join(PosSale, PosSaleLine.sale_id == PosSale.id)
        .where(PosSaleLine.tenant_id == tenant_id)
        .where(PosSaleLine.status == "NON_REUSABLE_LABEL")
        .where(PosSale.status == "PAID")
        .where(PosSaleLine.epc.is_not(None))
    ).all()
    epcs = {row.epc for row in sale_lines if row.epc}
    if not epcs:
        return []
    stock_rows = db.execute(
        select(StockItem.id, StockItem.epc, StockItem.status)
        .where(StockItem.tenant_id == tenant_id)
        .where(StockItem.epc.in_(epcs))
        .where(StockItem.status.notin_({"SOLD"}))
    ).all()
    findings = []
    for row in stock_rows:
        findings.append(
            IntegrityFinding(
                check_id="non_reusable_label_reuse",
                severity=SEVERITY_CRITICAL,
                tenant_id=tenant_id,
                message="NON_REUSABLE_LABEL EPC reused after sale.",
                entity="stock_items",
                entity_id=str(row.id),
                details={"epc": row.epc, "status": row.status},
            )
        )
    if findings:
        metrics.increment_invariant_violation("non_reusable_label_reuse", len(findings))
    return findings


def check_cash_session_open(db, tenant_id: str) -> list[IntegrityFinding]:
    rows = db.execute(
        select(
            PosCashSession.store_id,
            PosCashSession.cashier_user_id,
            func.count(PosCashSession.id).label("open_count"),
        )
        .where(PosCashSession.tenant_id == tenant_id, PosCashSession.status == "OPEN")
        .group_by(PosCashSession.store_id, PosCashSession.cashier_user_id)
        .having(func.count(PosCashSession.id) > 1)
    ).all()
    findings = []
    for row in rows:
        findings.append(
            IntegrityFinding(
                check_id="multiple_open_cash_sessions",
                severity=SEVERITY_CRITICAL,
                tenant_id=tenant_id,
                message="Multiple OPEN cash sessions for cashier/store.",
                entity="pos_cash_sessions",
                entity_id=None,
                details={
                    "store_id": str(row.store_id),
                    "cashier_user_id": str(row.cashier_user_id),
                    "open_count": int(row.open_count),
                },
            )
        )
    if findings:
        metrics.increment_invariant_violation("multiple_open_cash_sessions", len(findings))
    return findings


def check_paid_sale_totals(db, tenant_id: str) -> list[IntegrityFinding]:
    rows = db.execute(
        select(
            PosSale.id,
            PosSale.total_due,
            PosSale.paid_total,
            PosSale.balance_due,
            PosSale.change_due,
        )
        .where(PosSale.tenant_id == tenant_id)
        .where(PosSale.status == "PAID")
    ).all()
    findings = []
    for row in rows:
        total_due = Decimal(str(row.total_due))
        paid_total = Decimal(str(row.paid_total))
        balance_due = Decimal(str(row.balance_due))
        change_due = Decimal(str(row.change_due))
        expected_change = paid_total - total_due
        if balance_due > Decimal("0.01") or paid_total + Decimal("0.01") < total_due:
            inconsistent = True
        else:
            inconsistent = abs(expected_change - change_due) > Decimal("0.01")
        if inconsistent:
            findings.append(
                IntegrityFinding(
                    check_id="paid_sale_totals",
                    severity=SEVERITY_CRITICAL,
                    tenant_id=tenant_id,
                    message="PAID sale totals inconsistent.",
                    entity="pos_sales",
                    entity_id=str(row.id),
                    details={
                        "total_due": str(total_due),
                        "paid_total": str(paid_total),
                        "balance_due": str(balance_due),
                        "change_due": str(change_due),
                    },
                )
            )
    if findings:
        metrics.increment_invariant_violation("paid_sale_totals", len(findings))
    return findings


def check_transfer_fsm(db, tenant_id: str) -> list[IntegrityFinding]:
    rows = db.execute(
        select(
            Transfer.id,
            Transfer.status,
            Transfer.dispatched_at,
            Transfer.received_at,
            Transfer.canceled_at,
        )
        .where(Transfer.tenant_id == tenant_id)
    ).all()
    findings = []
    for row in rows:
        status = row.status
        dispatched_at = row.dispatched_at
        received_at = row.received_at
        canceled_at = row.canceled_at
        invalid = False
        if status == "DRAFT":
            invalid = any([dispatched_at, received_at, canceled_at])
        elif status == "DISPATCHED":
            invalid = dispatched_at is None or received_at is not None or canceled_at is not None
        elif status == "PARTIAL_RECEIVED":
            invalid = dispatched_at is None or received_at is not None or canceled_at is not None
        elif status == "RECEIVED":
            invalid = dispatched_at is None or received_at is None or canceled_at is not None
        elif status == "CANCELLED":
            invalid = canceled_at is None
        else:
            invalid = True
        if invalid:
            findings.append(
                IntegrityFinding(
                    check_id="transfer_fsm",
                    severity=SEVERITY_CRITICAL,
                    tenant_id=tenant_id,
                    message="Transfer state/timestamps inconsistent.",
                    entity="transfers",
                    entity_id=str(row.id),
                    details={
                        "status": status,
                        "dispatched_at": _format_datetime(dispatched_at),
                        "received_at": _format_datetime(received_at),
                        "canceled_at": _format_datetime(canceled_at),
                    },
                )
            )
    if findings:
        metrics.increment_invariant_violation("transfer_fsm", len(findings))
    return findings


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def run_integrity_checks(db, tenant_id: str) -> list[IntegrityFinding]:
    findings: list[IntegrityFinding] = []
    findings.extend(check_total_vendible_status(db, tenant_id))
    findings.extend(check_duplicate_epc(db, tenant_id))
    findings.extend(check_non_reusable_label_reuse(db, tenant_id))
    findings.extend(check_cash_session_open(db, tenant_id))
    findings.extend(check_paid_sale_totals(db, tenant_id))
    findings.extend(check_transfer_fsm(db, tenant_id))
    return findings
