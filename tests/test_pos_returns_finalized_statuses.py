from uuid import UUID

from app.aris3.db.models import PosSale
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def test_returns_endpoints_accept_legacy_finalized_status_case_insensitive(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="returns-finalized-status")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-RET-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=10.0,
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-RET-1", epc=None)],
        payments=[{"method": "CARD", "amount": 10, "authorization_code": "AUTH-RET-1"}],
    )
    sale_id = sale["header"]["id"]
    sale_line_id = sale["lines"][0]["id"]

    sale_row = db_session.query(PosSale).filter(PosSale.id == UUID(sale_id)).first()
    assert sale_row is not None
    sale_row.status = "completed"
    db_session.commit()

    eligibility = client.get(f"/aris3/pos/returns/eligibility?sale_id={sale_id}")
    assert eligibility.status_code == 200
    assert eligibility.json()["eligible"] is True

    payload = {
        "transaction_id": "txn-returns-status-check",
        "store_id": str(store.id),
        "sale_id": sale_id,
        "items": [{"sale_line_id": sale_line_id, "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
        "exchange_lines": [],
    }

    quote = client.post("/aris3/pos/returns/quote", json=payload)
    assert quote.status_code == 200
    draft = client.post("/aris3/pos/returns", json=payload)
    assert draft.status_code == 201


def test_exchange_action_accepts_legacy_finalized_status_case_insensitive(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exchange-finalized-status")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-OLD-FINAL",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-NEW-FINAL",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=12.0,
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-OLD-FINAL", epc=None)],
        payments=[{"method": "CARD", "amount": 10, "authorization_code": "AUTH-OLD-FINAL"}],
    )

    set_return_policy(
        client,
        token,
        {
            "allow_exchange": True,
            "allow_refund_cash": True,
            "allow_refund_card": True,
            "accepted_conditions": ["NEW"],
            "require_receipt": False,
            "restocking_fee_pct": 0,
        },
        idempotency_key="return-policy-finalized-status",
    )

    sale_id = sale["header"]["id"]
    sale_row = db_session.query(PosSale).filter(PosSale.id == UUID(sale_id)).first()
    assert sale_row is not None
    sale_row.status = "finalized"
    db_session.commit()

    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-finalized-status"},
        json={
            "transaction_id": "txn-exchange-finalized-status",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": sale["lines"][0]["id"], "qty": 1, "condition": "NEW"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-NEW-FINAL", "qty": 1}],
            "payments": [{"method": "CARD", "amount": 2, "authorization_code": "AUTH-DELTA-FINAL"}],
        },
    )
    assert response.status_code == 200
