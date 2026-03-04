from app.aris3.schemas.pos_returns import ReturnQuoteRequest
from app.aris3.services.pos_returns import compute_quote


def test_exchange_net_adjustment_positive():
    req = ReturnQuoteRequest(
        transaction_id='txn-1',
        store_id='store-1',
        sale_id='sale-1',
        items=[{'sale_line_id': 'l1', 'qty': 1, 'condition': 'NEW', 'resolution': 'REFUND'}],
        exchange_lines=[{'line_type': 'SKU', 'sku': 'SKU1', 'qty': 3}],
    )
    quote = compute_quote(req)
    assert str(quote.net_adjustment) == '20.00'
    assert quote.settlement_direction == 'CUSTOMER_PAYS'
