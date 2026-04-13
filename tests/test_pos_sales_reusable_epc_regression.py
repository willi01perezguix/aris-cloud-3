from __future__ import annotations

import uuid

from app.aris3.db.models import EpcAssignment, PosSaleLine, StockItem
from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def _create_draft_sale(client, token: str, store_id: str, lines: list[dict], txn_id: str):
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"idem-{txn_id}"},
        json=sale_payload(store_id, lines, transaction_id=txn_id),
    )
    assert response.status_code == 201
    return response.json()["header"]["id"]


def test_pos_sales_list_returns_rows_after_checkout(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-list")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-LIST-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=12.5,
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_draft_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, sku="SKU-LIST-1", epc=None)],
        "txn-list-create",
    )

    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-list-checkout"},
        json={
            "transaction_id": "txn-list-checkout",
            "action": "CHECKOUT",
            "receipt_number": "RCPT-LIST-1",
            "payments": [{"method": "CASH", "amount": "12.50"}],
        },
    )
    assert checkout.status_code == 200

    list_response = client.get(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}"},
        params={"receipt_number": "RCPT-LIST-1", "page": 1, "page_size": 20},
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] >= 1
    assert any(row["receipt_number"] == "RCPT-LIST-1" for row in payload["rows"])


def test_epc_checkout_releases_assignment_and_allows_epc_reuse(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="epc-reuse")
    token = login(client, user.username, "Pass1234!")

    stock = create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-EPC-REUSE",
        epc="EPC-REUSE-1",
        location_code="LOC-1",
        pool="P1",
        status="RFID",
        sale_price=20.0,
    )

    assignment = EpcAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        epc="EPC-REUSE-1",
        item_uid=stock.item_uid,
        active=True,
        status="ASSIGNED",
    )
    db_session.add(assignment)
    db_session.commit()

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_draft_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="EPC", qty=1, sku=None, epc="EPC-REUSE-1")],
        "txn-epc-reuse-create",
    )

    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-epc-reuse-checkout"},
        json={
            "transaction_id": "txn-epc-reuse-checkout",
            "action": "CHECKOUT",
            "payments": [{"method": "CASH", "amount": "20.00"}],
        },
    )
    assert checkout.status_code == 200

    sale_line_row = db_session.query(PosSaleLine).filter(PosSaleLine.sale_id == sale_id).one()
    assert sale_line_row.epc_at_sale == "EPC-REUSE-1"
    assert sale_line_row.item_uid == stock.item_uid

    sold_stock = db_session.query(StockItem).filter(StockItem.id == stock.id).one()
    assert sold_stock.status == "SOLD"
    assert sold_stock.epc is None

    released_assignment = db_session.query(EpcAssignment).filter(EpcAssignment.id == assignment.id).one()
    assert released_assignment.active is False
    assert released_assignment.status == "RELEASED"
    assert released_assignment.released_at is not None

    reused_stock = create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-EPC-REUSED",
        epc="EPC-REUSE-1",
        location_code="LOC-2",
        pool="P2",
        status="RFID",
        sale_price=22.0,
    )
    assert reused_stock.epc == "EPC-REUSE-1"


def test_sku_checkout_marks_stock_as_sold(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="sku-checkout")
    token = login(client, user.username, "Pass1234!")

    first = create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CHECK-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=10.0,
    )
    second = create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CHECK-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=10.0,
    )

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_draft_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=2, sku="SKU-CHECK-1", epc=None)],
        "txn-sku-check-create",
    )

    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-sku-checkout"},
        json={
            "transaction_id": "txn-sku-checkout",
            "action": "CHECKOUT",
            "payments": [{"method": "CASH", "amount": "20.00"}],
        },
    )
    assert checkout.status_code == 200

    sold_rows = (
        db_session.query(StockItem)
        .filter(StockItem.id.in_([first.id, second.id]))
        .filter(StockItem.status == "SOLD")
        .count()
    )
    assert sold_rows == 2
