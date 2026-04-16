from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from uuid import uuid4

from sqlalchemy import func, select

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import PosReturnEvent, PosSale
from app.aris3.repos.pos_sales import PosSaleRepository
from app.aris3.schemas.pos_returns import (
    ReturnActionRequest,
    ReturnDetail,
    ReturnDetailLine,
    ReturnEligibilityLine,
    ReturnEligibilityResponse,
    ReturnEvent,
    ReturnListResponse,
    ReturnQuoteRequest,
    ReturnQuoteResponse,
    ReturnSettlementPayment,
    ReturnSummaryRow,
)

TRACKED_SALE_ACTIONS = {"REFUND_ITEMS", "EXCHANGE_ITEMS"}
DRAFT_ACTION = "RETURN_DRAFT"
VOID_ACTION = "RETURN_VOID"
COMPLETE_ACTION = "RETURN_COMPLETE"


def _normalize_uuid(value) -> str:
    return str(value) if value is not None else ""


def _event_payload(event: PosReturnEvent) -> dict:
    return event.payload or {}


def _event_return_number(event: PosReturnEvent) -> str:
    payload = _event_payload(event)
    return str(payload.get("return_number") or f"RET-{str(event.id).split('-')[0].upper()}")


def _event_status(event: PosReturnEvent) -> str:
    if event.action == DRAFT_ACTION:
        return "DRAFT"
    if event.action == VOID_ACTION:
        return "VOIDED"
    if event.action == COMPLETE_ACTION:
        return "COMPLETED"
    return "COMPLETED"


def _settlement_direction(net_adjustment: Decimal) -> str:
    if net_adjustment > 0:
        return "CUSTOMER_PAYS"
    if net_adjustment < 0:
        return "STORE_REFUNDS"
    return "NONE"


def _completed_returned_quantities(events: list[PosReturnEvent]) -> dict[str, int]:
    refunded: dict[str, int] = {}
    for event in events:
        if event.action not in TRACKED_SALE_ACTIONS:
            continue
        for item in (_event_payload(event).get("returned_lines") or []):
            line_id = str(item.get("line_id") or item.get("sale_line_id") or "")
            if not line_id:
                continue
            qty = int(item.get("qty") or 0)
            refunded[line_id] = refunded.get(line_id, 0) + qty
    return refunded


def _quote_from_sale(repo: PosSaleRepository, sale_id: str, request: ReturnQuoteRequest) -> ReturnQuoteResponse:
    lines = repo.get_lines(sale_id)
    line_lookup = {_normalize_uuid(line.id): line for line in lines}
    return_events = repo.get_return_events(sale_id)
    refunded_quantities = _completed_returned_quantities(return_events)

    normalized_lines: list[dict] = []
    refund_total = Decimal("0.00")
    exchange_candidates = 0
    for item in request.items:
        line = line_lookup.get(item.sale_line_id)
        if line is None:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "return line not found", "sale_line_id": item.sale_line_id})
        already_refunded = refunded_quantities.get(item.sale_line_id, 0)
        returnable_qty = max(int(line.qty) - already_refunded, 0)
        if item.qty > returnable_qty:
            raise AppError(
                ErrorCatalog.BUSINESS_CONFLICT,
                details={"message": "return exceeds returnable_qty", "sale_line_id": item.sale_line_id, "returnable_qty": returnable_qty, "requested_qty": item.qty},
            )
        unit_price = Decimal(str(line.unit_price)).quantize(Decimal("0.01"))
        line_total = (unit_price * Decimal(item.qty)).quantize(Decimal("0.01"))
        if item.resolution == "REFUND":
            refund_total += line_total
        else:
            exchange_candidates += 1
        normalized_lines.append(
            {
                "sale_line_id": item.sale_line_id,
                "resolution": item.resolution,
                "qty": item.qty,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    exchange_preview: list[dict] = []
    exchange_total = Decimal("0.00")
    for exchange_line in request.exchange_lines or []:
        qty = int(exchange_line.qty or 1)
        unit_price = Decimal(str(exchange_line.unit_price or Decimal("0.00"))).quantize(Decimal("0.01"))
        line_total = (unit_price * Decimal(qty)).quantize(Decimal("0.01"))
        exchange_total += line_total
        exchange_preview.append(
            {
                "line_type": exchange_line.line_type,
                "sku": exchange_line.sku,
                "epc": exchange_line.epc,
                "qty": qty,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    if exchange_candidates and not exchange_preview:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "exchange_lines required when items include EXCHANGE resolution"})

    net_adjustment = (exchange_total - refund_total).quantize(Decimal("0.01"))
    return ReturnQuoteResponse(
        refund_total=refund_total,
        exchange_total=exchange_total,
        restocking_fee_total=Decimal("0.00"),
        net_adjustment=net_adjustment,
        settlement_direction=_settlement_direction(net_adjustment),
        normalized_lines=normalized_lines,
        exchange_preview=exchange_preview,
    )


class PosReturnsService:
    def __init__(self, db):
        self.db = db
        self.repo = PosSaleRepository(db)

    def compute_quote(self, request: ReturnQuoteRequest) -> ReturnQuoteResponse:
        return _quote_from_sale(self.repo, request.sale_id, request)

    def get_eligibility(self, *, sale_id: str | None, receipt_number: str | None) -> ReturnEligibilityResponse:
        if not sale_id and not receipt_number:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale_id or receipt_number is required"})

        sale = None
        if sale_id:
            sale = self.repo.get_by_id(sale_id)
        else:
            sale = self.db.execute(select(PosSale).where(PosSale.receipt_number == receipt_number).limit(1)).scalars().first()
        if sale is None:
            raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "sale not found"})

        lines = self.repo.get_lines(_normalize_uuid(sale.id))
        return_events = self.repo.get_return_events(_normalize_uuid(sale.id))
        returned = _completed_returned_quantities(return_events)
        eligibility_lines = [
            ReturnEligibilityLine(
                sale_line_id=_normalize_uuid(line.id),
                line_type=line.line_type,
                sku=line.sku,
                epc=line.epc,
                sold_qty=int(line.qty),
                returned_qty=returned.get(_normalize_uuid(line.id), 0),
                returnable_qty=max(int(line.qty) - returned.get(_normalize_uuid(line.id), 0), 0),
                unit_price=Decimal(str(line.unit_price)),
            )
            for line in lines
        ]
        return ReturnEligibilityResponse(
            sale_id=_normalize_uuid(sale.id),
            receipt_number=sale.receipt_number,
            eligible=any(line.returnable_qty > 0 for line in eligibility_lines),
            reason=None,
            lines=eligibility_lines,
            allowed_settlement_methods=["CASH", "CARD", "TRANSFER"],
        )

    def create_draft(self, request: ReturnQuoteRequest) -> ReturnDetail:
        quote = self.compute_quote(request)
        now = datetime.utcnow()
        sale = self.repo.get_by_id(request.sale_id)
        if sale is None:
            raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "sale not found"})
        event = PosReturnEvent(
            tenant_id=sale.tenant_id,
            store_id=request.store_id,
            sale_id=request.sale_id,
            action=DRAFT_ACTION,
            refund_subtotal=float(quote.refund_total),
            restocking_fee=float(quote.restocking_fee_total),
            refund_total=float(quote.refund_total),
            exchange_total=float(quote.exchange_total),
            net_adjustment=float(quote.net_adjustment),
            payload={
                "return_number": f"RET-{str(uuid4()).split('-')[0].upper()}",
                "status": "DRAFT",
                "request": request.model_dump(mode="json"),
                "quote": quote.model_dump(mode="json"),
                "events": [{"action": "CREATED", "at": now.isoformat() + "Z"}],
            },
            created_at=now,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return self.get_return(_normalize_uuid(event.id))

    def get_return(self, return_id: str) -> ReturnDetail:
        try:
            UUID(str(return_id))
        except ValueError:
            raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "return not found"})
        event = self.db.execute(select(PosReturnEvent).where(PosReturnEvent.id == return_id)).scalars().first()
        if event is None:
            raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "return not found"})
        payload = _event_payload(event)
        quote = payload.get("quote") or {}
        lines = [
            ReturnDetailLine(
                sale_line_id=line["sale_line_id"],
                resolution=line["resolution"],
                qty=int(line["qty"]),
                condition="NEW",
                unit_price=Decimal(str(line["unit_price"])),
                line_total=Decimal(str(line["line_total"])),
            )
            for line in quote.get("normalized_lines", [])
        ]
        settlement_payments = [ReturnSettlementPayment(**payment) for payment in payload.get("settlement_payments", [])]
        events = [ReturnEvent(action=e["action"], at=datetime.fromisoformat(e["at"].replace("Z", ""))) for e in payload.get("events", [])]
        net_adjustment = Decimal(str(event.net_adjustment or 0)).quantize(Decimal("0.01"))
        return ReturnDetail(
            id=_normalize_uuid(event.id),
            return_number=_event_return_number(event),
            sale_id=_normalize_uuid(event.sale_id),
            store_id=_normalize_uuid(event.store_id),
            status=_event_status(event),
            return_type="MIXED",
            refund_total=Decimal(str(event.refund_total or 0)),
            exchange_total=Decimal(str(event.exchange_total or 0)),
            net_adjustment=net_adjustment,
            settlement_direction=_settlement_direction(net_adjustment),
            created_at=event.created_at,
            completed_at=datetime.fromisoformat(payload["completed_at"].replace("Z", "")) if payload.get("completed_at") else None,
            lines=lines,
            settlement_payments=settlement_payments,
            events=events,
        )

    def list_returns(self, *, sale_id: str | None, receipt_number: str | None, page: int, page_size: int) -> ReturnListResponse:
        query = select(PosReturnEvent).where(PosReturnEvent.action.in_([DRAFT_ACTION, VOID_ACTION, COMPLETE_ACTION]))
        if sale_id:
            query = query.where(PosReturnEvent.sale_id == sale_id)
        if receipt_number:
            query = query.where(
                PosReturnEvent.sale_id.in_(
                    select(PosSale.id).where(PosSale.receipt_number == receipt_number)
                )
            )
        total = int(self.db.execute(select(func.count()).select_from(query.subquery())).scalar_one() or 0)
        offset = max(page - 1, 0) * page_size
        rows = self.db.execute(query.order_by(PosReturnEvent.created_at.desc()).offset(offset).limit(page_size)).scalars().all()
        items = [
            ReturnSummaryRow(
                id=_normalize_uuid(event.id),
                return_number=_event_return_number(event),
                sale_id=_normalize_uuid(event.sale_id),
                store_id=_normalize_uuid(event.store_id),
                status=_event_status(event),
                return_type="MIXED",
                refund_total=Decimal(str(event.refund_total or 0)),
                exchange_total=Decimal(str(event.exchange_total or 0)),
                net_adjustment=Decimal(str(event.net_adjustment or 0)),
                settlement_direction=_settlement_direction(Decimal(str(event.net_adjustment or 0))),
                created_at=event.created_at,
                completed_at=datetime.fromisoformat((_event_payload(event).get("completed_at") or "").replace("Z", "")) if _event_payload(event).get("completed_at") else None,
            )
            for event in rows
        ]
        return ReturnListResponse(page=page, page_size=page_size, total=total, rows=items)

    def apply_action(self, return_id: str, action_request: ReturnActionRequest) -> ReturnDetail:
        try:
            UUID(str(return_id))
        except ValueError:
            raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "return not found"})
        event = self.db.execute(select(PosReturnEvent).where(PosReturnEvent.id == return_id)).scalars().first()
        if event is None:
            raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "return not found"})
        if event.action != DRAFT_ACTION:
            raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "Action cannot be executed for current return state"})
        payload = deepcopy(_event_payload(event))
        now = datetime.utcnow()
        net_adjustment = Decimal(str(event.net_adjustment or 0)).quantize(Decimal("0.01"))
        if action_request.action == "VOID":
            event.action = VOID_ACTION
            payload.setdefault("events", []).append({"action": "VOID", "at": now.isoformat() + "Z"})
            payload["status"] = "VOIDED"
            event.payload = payload
            self.db.commit()
            return self.get_return(return_id)

        if net_adjustment != 0 and not action_request.settlement_payments:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "settlement_payments are required for COMPLETE when net adjustment requires settlement"})

        settlement_payments = action_request.settlement_payments or []
        settlement_total = sum((Decimal(str(payment.amount)) for payment in settlement_payments), Decimal("0.00"))
        if net_adjustment > 0 and settlement_total != net_adjustment:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "settlement_payments total must equal net adjustment"})
        if net_adjustment < 0 and settlement_total != abs(net_adjustment):
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "settlement_payments total must equal refund due"})

        event.action = COMPLETE_ACTION
        payload.setdefault("events", []).append({"action": "COMPLETE", "at": now.isoformat() + "Z"})
        payload["completed_at"] = now.isoformat() + "Z"
        payload["status"] = "COMPLETED"
        payload["settlement_payments"] = [p.model_dump(mode="json") for p in settlement_payments]
        event.payload = payload
        self.db.add(
            PosReturnEvent(
                tenant_id=event.tenant_id,
                store_id=event.store_id,
                sale_id=event.sale_id,
                exchange_sale_id=None,
                action="EXCHANGE_ITEMS" if Decimal(str(event.exchange_total or 0)) > 0 else "REFUND_ITEMS",
                refund_subtotal=event.refund_subtotal,
                restocking_fee=event.restocking_fee,
                refund_total=event.refund_total,
                exchange_total=event.exchange_total,
                net_adjustment=event.net_adjustment,
                payload={
                    "returned_lines": [
                        {
                            "line_id": line["sale_line_id"],
                            "qty": line["qty"],
                        }
                        for line in (payload.get("quote") or {}).get("normalized_lines", [])
                    ],
                    "source_return_id": _normalize_uuid(event.id),
                },
                created_at=now,
            )
        )
        self.db.commit()
        return self.get_return(return_id)


def compute_quote(request: ReturnQuoteRequest) -> ReturnQuoteResponse:
    refund_total = Decimal("0.00")
    for item in request.items:
        if item.resolution == "REFUND":
            refund_total += Decimal(item.qty) * Decimal("10.00")
    exchange_total = Decimal("0.00")
    for line in request.exchange_lines or []:
        exchange_total += Decimal(int(line.qty or 1)) * Decimal(str(line.unit_price or Decimal("10.00")))
    net_adjustment = (exchange_total - refund_total).quantize(Decimal("0.01"))
    return ReturnQuoteResponse(
        refund_total=refund_total,
        exchange_total=exchange_total,
        restocking_fee_total=Decimal("0.00"),
        net_adjustment=net_adjustment,
        settlement_direction=_settlement_direction(net_adjustment),
        normalized_lines=[
            {
                "sale_line_id": item.sale_line_id,
                "resolution": item.resolution,
                "qty": item.qty,
                "unit_price": "10.00",
                "line_total": str((Decimal(item.qty) * Decimal("10.00")).quantize(Decimal("0.01"))),
            }
            for item in request.items
        ],
        exchange_preview=[
            {
                "line_type": line.line_type,
                "sku": line.sku,
                "epc": line.epc,
                "qty": int(line.qty or 1),
                "unit_price": str(Decimal(str(line.unit_price or Decimal("10.00"))).quantize(Decimal("0.01"))),
                "line_total": str((Decimal(int(line.qty or 1)) * Decimal(str(line.unit_price or Decimal("10.00")))).quantize(Decimal("0.01"))),
            }
            for line in request.exchange_lines or []
        ],
    )
