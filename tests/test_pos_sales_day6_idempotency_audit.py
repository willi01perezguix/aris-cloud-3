from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.db.models import AuditEvent
from tests.pos_sales_helpers import (
    create_tenant_user,
    login,
    sale_line,
    sale_payload,
    seed_defaults,
)


def test_pos_sale_idempotency_replay_and_conflict(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-idem")
    token = login(client, user.username, "Pass1234!")

    payload = sale_payload(
        str(store.id),
        [
            sale_line(
                line_type="SKU",
                qty=1,
                unit_price=7.0,
                sku="SKU-1",
                epc=None,
                status="PENDING",
            )
        ],
        transaction_id="txn-idem-1",
    )
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-idem"}

    first = client.post("/aris3/pos/sales", headers=headers, json=payload)
    assert first.status_code == 201

    replay = client.post("/aris3/pos/sales", headers=headers, json=payload)
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.headers.get("X-Idempotency-Result") == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict = client.post(
        "/aris3/pos/sales",
        headers=headers,
        json={**payload, "transaction_id": "txn-idem-2"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code


def test_pos_sale_audit_event_created(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-audit")
    token = login(client, user.username, "Pass1234!")

    payload = sale_payload(
        str(store.id),
        [
            sale_line(
                line_type="SKU",
                qty=1,
                unit_price=4.0,
                sku="SKU-2",
                epc=None,
                status="PENDING",
            )
        ],
        transaction_id="txn-audit-1",
    )
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-audit"},
        json=payload,
    )
    assert response.status_code == 201

    event = db_session.query(AuditEvent).filter(AuditEvent.action == "pos_sale.create").first()
    assert event is not None
    assert event.result == "success"
