from __future__ import annotations

from app.aris3.db.models import PosSale
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    seed_defaults,
)


def _setup_paid_sale(client, db_session, *, suffix: str, sold_price: float = 100.0):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix=suffix)
    token = login(client, user.username, "Pass1234!")
    sku = f"SKU-{suffix.upper()}"
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        sku=sku,
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=sold_price,
    )
    open_cash_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
    )
    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=sold_price, sku=sku, epc=None)],
        payments=[{"method": "CASH", "amount": f"{sold_price:.2f}"}],
        create_txn=f"txn-sale-create-{suffix}",
        checkout_txn=f"txn-sale-checkout-{suffix}",
        idempotency_key=f"idem-sale-create-{suffix}",
        checkout_idempotency_key=f"idem-sale-checkout-{suffix}",
    )
    return token, sale, tenant, store


def test_return_quote_refund_without_exchange_lines_is_supported(client, db_session):
    token, sale, _tenant, _store = _setup_paid_sale(client, db_session, suffix="quote-refund-no-exchange-lines", sold_price=33.0)

    response = client.post(
        "/aris3/pos/returns/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-refund-quote-no-exchange-lines",
            "store_id": sale["header"]["store_id"],
            "sale_id": sale["header"]["id"],
            "items": [{"sale_line_id": sale["lines"][0]["id"], "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refund_total"] == "33.00"
    assert payload["exchange_total"] == "0.00"
    assert payload["net_adjustment"] == "-33.00"
    assert payload["settlement_direction"] == "STORE_REFUNDS"


def test_return_quote_exchange_resolution_requires_exchange_lines(client, db_session):
    token, sale, _tenant, _store = _setup_paid_sale(client, db_session, suffix="quote-exchange-lines-required", sold_price=40.0)

    response = client.post(
        "/aris3/pos/returns/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-exchange-quote-missing-replacement",
            "store_id": sale["header"]["store_id"],
            "sale_id": sale["header"]["id"],
            "items": [{"sale_line_id": sale["lines"][0]["id"], "qty": 1, "condition": "NEW", "resolution": "EXCHANGE"}],
        },
    )

    assert response.status_code == 422
    assert response.json()["details"]["message"] == "exchange_lines required when items include EXCHANGE resolution"


def test_return_quote_exchange_delta_direction_cases(client, db_session):
    token, sale, tenant, store = _setup_paid_sale(client, db_session, suffix="quote-delta-cases", sold_price=10.0)
    line_id = sale["lines"][0]["id"]

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        sku="SKU-DELTA-9",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=9.0,
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        sku="SKU-DELTA-10",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=10.0,
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        sku="SKU-DELTA-12",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=12.0,
    )

    def quote_for_sku(sku: str):
        return client.post(
            "/aris3/pos/returns/quote",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "transaction_id": f"txn-quote-{sku}",
                "store_id": sale["header"]["store_id"],
                "sale_id": sale["header"]["id"],
                "items": [{"sale_line_id": line_id, "qty": 1, "condition": "NEW", "resolution": "EXCHANGE"}],
                "exchange_lines": [{"line_type": "SKU", "sku": sku, "qty": 1}],
            },
        )

    cheaper = quote_for_sku("SKU-DELTA-9")
    assert cheaper.status_code == 200
    assert cheaper.json()["settlement_direction"] == "STORE_REFUNDS"

    equal = quote_for_sku("SKU-DELTA-10")
    assert equal.status_code == 200
    assert equal.json()["settlement_direction"] == "NONE"

    expensive = quote_for_sku("SKU-DELTA-12")
    assert expensive.status_code == 200
    assert expensive.json()["settlement_direction"] == "CUSTOMER_PAYS"


def test_return_quote_accepts_finalized_sale_statuses_case_insensitively(client, db_session):
    token, sale, _tenant, _store = _setup_paid_sale(client, db_session, suffix="quote-status-case-insensitive", sold_price=17.0)

    sale_row = db_session.query(PosSale).filter(PosSale.id == sale["header"]["id"]).first()
    assert sale_row is not None
    sale_row.status = "paid"
    db_session.add(sale_row)
    db_session.commit()

    response = client.post(
        "/aris3/pos/returns/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-quote-case-insensitive",
            "store_id": sale["header"]["store_id"],
            "sale_id": sale["header"]["id"],
            "items": [{"sale_line_id": sale["lines"][0]["id"], "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["settlement_direction"] == "STORE_REFUNDS"
