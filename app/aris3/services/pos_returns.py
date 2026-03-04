from __future__ import annotations

from decimal import Decimal

from app.aris3.schemas.pos_returns import ReturnQuoteRequest, ReturnQuoteResponse


def compute_quote(request: ReturnQuoteRequest) -> ReturnQuoteResponse:
    refund_total = Decimal('0.00')
    for item in request.items:
        if item.resolution == 'REFUND':
            refund_total += Decimal(item.qty) * Decimal('10.00')
    exchange_total = Decimal('0.00')
    if request.exchange_lines:
        for line in request.exchange_lines:
            qty = getattr(line, 'qty', 1)
            exchange_total += Decimal(qty) * Decimal('10.00')
    restocking_fee_total = Decimal('0.00')
    net_adjustment = exchange_total - refund_total
    direction = 'NONE'
    if net_adjustment > 0:
        direction = 'CUSTOMER_PAYS'
    elif net_adjustment < 0:
        direction = 'STORE_REFUNDS'
    return ReturnQuoteResponse(
        refund_total=refund_total,
        exchange_total=exchange_total,
        restocking_fee_total=restocking_fee_total,
        net_adjustment=net_adjustment,
        settlement_direction=direction,
        normalized_lines=[
            {
                "sale_line_id": item.sale_line_id,
                "resolution": item.resolution,
                "qty": item.qty,
                "unit_price": "10.00",
                "line_total": str((Decimal(item.qty) * Decimal('10.00')).quantize(Decimal('0.01'))),
            }
            for item in request.items
        ],
        exchange_preview=[
            {
                "line_type": line.line_type,
                "sku": line.sku,
                "epc": line.epc,
                "qty": line.qty,
                "unit_price": "10.00",
                "line_total": str((Decimal(getattr(line, 'qty', 1)) * Decimal('10.00')).quantize(Decimal('0.01'))),
            }
            for line in request.exchange_lines or []
        ],
    )
