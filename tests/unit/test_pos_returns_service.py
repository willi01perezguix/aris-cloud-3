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


def test_refund_only_quote_sets_store_refunds_direction():
    req = ReturnQuoteRequest(
        transaction_id='txn-2',
        store_id='store-1',
        sale_id='sale-1',
        items=[{'sale_line_id': 'l1', 'qty': 2, 'condition': 'NEW', 'resolution': 'REFUND'}],
        exchange_lines=[],
    )
    quote = compute_quote(req)
    assert str(quote.refund_total) == '20.00'
    assert str(quote.net_adjustment) == '-20.00'
    assert quote.settlement_direction == 'STORE_REFUNDS'


def test_balanced_quote_sets_none_direction():
    req = ReturnQuoteRequest(
        transaction_id='txn-3',
        store_id='store-1',
        sale_id='sale-1',
        items=[{'sale_line_id': 'l1', 'qty': 1, 'condition': 'NEW', 'resolution': 'REFUND'}],
        exchange_lines=[{'line_type': 'SKU', 'sku': 'SKU1', 'qty': 1, 'unit_price': '10.00'}],
    )
    quote = compute_quote(req)
    assert str(quote.net_adjustment) == '0.00'
    assert quote.settlement_direction == 'NONE'
