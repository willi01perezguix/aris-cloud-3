from uuid import UUID

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.db.models import AuditEvent
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def test_refund_idempotency_and_audit(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="refund-idem")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-IDEM",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=9.0, sku="SKU-IDEM", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 9, "authorization_code": "AUTH-IDEM"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token,
        {
            "allow_refund_card": True,
            "require_receipt": False,
            "accepted_conditions": ["NEW"],
        },
    )

    payload = {
        "transaction_id": "txn-refund-idem-1",
        "action": "REFUND_ITEMS",
        "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
        "refund_payments": [{"method": "CARD", "amount": 9, "authorization_code": "AUTH-IDEM-R"}],
    }
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-idem-key"}

    first = client.post(f"/aris3/pos/sales/{sale['header']['id']}/actions", headers=headers, json=payload)
    assert first.status_code == 200

    replay = client.post(f"/aris3/pos/sales/{sale['header']['id']}/actions", headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert replay.headers.get("X-Idempotency-Result") == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers=headers,
        json={**payload, "transaction_id": "txn-refund-idem-2"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.action == "pos_sale.refund_items", AuditEvent.entity_id == str(UUID(sale["header"]["id"])))
        .first()
    )
    assert event is not None
    assert event.result == "success"
