from datetime import datetime

from tests.pos_sales_helpers import create_paid_sale, create_stock_item, create_tenant_user, login, open_cash_session, sale_line, seed_defaults


def _create_paid_sale_with_receipt(client, db_session, token: str, tenant_id: str, store_id: str, user_id: str, *, sku: str, receipt: str):
    create_stock_item(
        db_session,
        tenant_id=tenant_id,
        sku=sku,
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=tenant_id, store_id=store_id, cashier_user_id=user_id)
    return create_paid_sale(
        client,
        token,
        store_id,
        [sale_line(line_type="SKU", qty=1, unit_price=25.0, sku=sku, epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 25}],
        create_txn=f"create-{receipt}",
        checkout_txn=f"checkout-{receipt}",
        idempotency_key=f"ik-create-{receipt}",
        checkout_idempotency_key=f"ik-checkout-{receipt}",
        receipt_number=receipt,
    )


def test_sales_list_filters_receipt_status_dates_and_scope(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="sale-search")
    other_tenant, other_store, _other_store_b, other_user = create_tenant_user(db_session, suffix="sale-search-b")
    token = login(client, user.username, "Pass1234!")
    other_token = login(client, other_user.username, "Pass1234!")

    sale_a = _create_paid_sale_with_receipt(
        client, db_session, token, str(tenant.id), str(store.id), str(user.id), sku="SKU-SEA-1", receipt="RCPT-SEA-1"
    )
    _create_paid_sale_with_receipt(
        client, db_session, token, str(tenant.id), str(store.id), str(user.id), sku="SKU-SEA-2", receipt="RCPT-SEA-2"
    )
    _create_paid_sale_with_receipt(
        client,
        db_session,
        other_token,
        str(other_tenant.id),
        str(other_store.id),
        str(other_user.id),
        sku="SKU-OTHER-1",
        receipt="RCPT-OTHER-1",
    )

    resp = client.get(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}"},
        params={"receipt_number": "RCPT-SEA-1", "status": "PAID", "page": 1, "page_size": 10},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["rows"][0]["id"] == sale_a["header"]["id"]
    assert body["rows"][0]["receipt_number"] == "RCPT-SEA-1"

    # date window must include current paid sale
    today = datetime.utcnow().date().isoformat()
    resp = client.get(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}"},
        params={"checked_out_from": today, "checked_out_to": today, "q": "SKU-SEA", "page": 1, "page_size": 50},
    )
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 2
    assert all(row["store_id"] == str(store.id) for row in rows)


def test_sale_detail_exposes_receipt_and_returnable_quantities(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="sale-detail-returnable")
    token = login(client, user.username, "Pass1234!")

    sale = _create_paid_sale_with_receipt(
        client,
        db_session,
        token,
        str(tenant.id),
        str(store.id),
        str(user.id),
        sku="SKU-R-1",
        receipt="RCPT-R-1",
    )
    line = sale["lines"][0]

    refund = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-refund-r1"},
        json={
            "transaction_id": "txn-refund-r1",
            "action": "REFUND_ITEMS",
            "receipt_number": "RCPT-R-1",
            "return_items": [{"line_id": line["id"], "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CASH", "amount": "25.00"}],
        },
    )
    assert refund.status_code == 200

    detail = client.get(f"/aris3/pos/sales/{sale['header']['id']}", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    body = detail.json()
    assert body["header"]["receipt_number"] == "RCPT-R-1"
    assert body["lines"][0]["returned_qty"] == 1
    assert body["lines"][0]["returnable_qty"] == 0
