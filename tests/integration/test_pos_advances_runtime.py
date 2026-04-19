from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.aris3.db.models import DrawerEvent, PosAdvance, PosCashMovement, PosSale
from tests.pos_sales_helpers import create_stock_item, create_tenant_user, login, open_cash_session, sale_line, sale_payload, seed_defaults


LEGAL_NOTICE = (
    "Este anticipo vence a los 60 días de su emisión. Pasada la fecha, el saldo caduca y no es reembolsable. "
    "El consumo debe ser por el total del monto."
)


def _issue_advance(client, token: str, store_id: str, transaction_id: str, amount: str = "100.00") -> dict:
    response = client.post(
        "/aris3/pos/advances",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": transaction_id,
            "store_id": store_id,
            "customer_name": "Cliente QA",
            "amount": amount,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200
    return response.json()


def _create_sale(db_session, *, tenant_id: str, store_id: str, total_due: str = "150.00") -> PosSale:
    sale = PosSale(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        store_id=UUID(store_id),
        status="PAID",
        total_due=float(total_due),
        paid_total=float(total_due),
        balance_due=0.0,
        change_due=0.0,
    )
    db_session.add(sale)
    db_session.commit()
    return sale


def test_advances_runtime_flow_contract(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-runtime")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    created = _issue_advance(client, token, str(store.id), "txn-adv-create", amount="100.00")
    issued_at = datetime.fromisoformat(created["issued_at"].replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))

    assert created["status"] == "ACTIVE"
    assert created["advance_number"] >= 1
    assert created["barcode_value"].startswith("ADV-")
    assert created["barcode_type"] == "CODE128"
    assert created["legal_notice"] == LEGAL_NOTICE
    assert (expires_at.date() - issued_at.date()).days == 60

    lookup = client.get(
        "/aris3/pos/advances/lookup",
        headers={"Authorization": f"Bearer {token}"},
        params={"code": str(created["advance_number"])},
    )
    assert lookup.status_code == 200
    assert lookup.json()["found"] is True
    assert lookup.json()["advance"]["id"] == created["id"]

    detail = client.get(f"/aris3/pos/advances/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]

    consume_low = client.post(
        f"/aris3/pos/advances/{created['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-consume-low",
            "action": "CONSUME",
            "sale_total": "99.99",
        },
    )
    assert consume_low.status_code == 422

    still_active = client.get(f"/aris3/pos/advances/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    assert still_active.status_code == 200
    assert still_active.json()["status"] == "ACTIVE"

    linked_sale = _create_sale(db_session, tenant_id=str(tenant.id), store_id=str(store.id), total_due="150.00")
    consume_high = client.post(
        f"/aris3/pos/advances/{created['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-consume-high",
            "action": "CONSUME",
            "sale_total": "150.00",
            "sale_id": str(linked_sale.id),
        },
    )
    assert consume_high.status_code == 200
    payload = consume_high.json()
    assert payload["status"] == "CONSUMED"
    assert payload["consumed_sale_id"] == str(linked_sale.id)
    assert Decimal(payload["applied_amount"]) == Decimal("100.00")
    assert Decimal(payload["remaining_amount_to_charge"]) == Decimal("50.00")

    consume_twice = client.post(
        f"/aris3/pos/advances/{created['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-consume-twice",
            "action": "CONSUME",
            "sale_total": "150.00",
        },
    )
    assert consume_twice.status_code == 409


def test_advances_consume_sale_id_validation_and_lookup(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-runtime-sale-id")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    invalid_format = _issue_advance(client, token, str(store.id), "txn-adv-sale-id-invalid", amount="50.00")
    invalid_format_response = client.post(
        f"/aris3/pos/advances/{invalid_format['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-adv-sale-id-invalid-consume", "action": "CONSUME", "sale_total": "50.00", "sale_id": "qa-sale-exact-005"},
    )
    assert invalid_format_response.status_code == 422
    assert invalid_format_response.json()["code"] == "VALIDATION_ERROR"

    nonexistent_sale = _issue_advance(client, token, str(store.id), "txn-adv-sale-id-missing", amount="50.00")
    nonexistent_response = client.post(
        f"/aris3/pos/advances/{nonexistent_sale['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-sale-id-missing-consume",
            "action": "CONSUME",
            "sale_total": "50.00",
            "sale_id": "11111111-1111-4111-8111-111111111111",
        },
    )
    assert nonexistent_response.status_code == 404
    assert nonexistent_response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_checkout_with_advance_is_atomic_and_followup_consume_conflicts(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-runtime-checkout-atomic")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    advance = _issue_advance(client, token, str(store.id), "txn-adv-runtime-checkout-atomic", amount="30.00")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        sku="SKU-ADV-ATOMIC",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        sku="SKU-ADV-ATOMIC",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-adv-runtime-checkout-atomic-create"},
        json=sale_payload(
            str(store.id),
            [sale_line(line_type="SKU", qty=2, sku="SKU-ADV-ATOMIC", epc=None, unit_price=15.0)],
            transaction_id="txn-adv-runtime-checkout-atomic-create",
        ),
    )
    assert create_sale.status_code == 201
    sale_id = create_sale.json()["header"]["id"]

    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-adv-runtime-checkout-atomic"},
        json={
            "transaction_id": "txn-adv-runtime-checkout-atomic",
            "action": "CHECKOUT",
            "payments": [{"method": "ADVANCE", "amount": "30.00", "reference_code": advance["barcode_value"]}],
        },
    )
    assert checkout.status_code == 200

    refreshed = db_session.query(PosAdvance).filter(PosAdvance.id == advance["id"]).one()
    assert refreshed.status == "CONSUMED"
    assert str(refreshed.consumed_sale_id) == sale_id

    followup_consume = client.post(
        f"/aris3/pos/advances/{advance['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-adv-runtime-checkout-followup", "action": "CONSUME", "sale_id": sale_id},
    )
    assert followup_consume.status_code == 409
    assert followup_consume.json()["code"] == "BUSINESS_CONFLICT"


def test_issue_advance_cash_returns_drawer_instruction_contract(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-runtime-drawer-instruction")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    issued = _issue_advance(client, token, str(store.id), "txn-adv-runtime-drawer-instruction", amount="55.00")
    assert issued["drawer_open_required"] is True
    instruction = issued["drawer_event_instruction"]
    assert instruction["already_recorded"] is True
    assert instruction["drawer_event_id"]
    assert instruction["event_type"] == "CASH_IN_DRAWER_OPEN"
    assert instruction["movement_type"] == "CASH_IN"
    assert "Do not call /aris3/pos/drawer/events" in instruction["next_step"]

    drawer_event = db_session.query(DrawerEvent).filter(DrawerEvent.id == instruction["drawer_event_id"]).one()
    assert drawer_event is not None
    assert drawer_event.event_type == "CASH_IN_DRAWER_OPEN"


def test_advances_refund_expiration_alerts_and_concurrency(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-runtime-2")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    to_refund = _issue_advance(client, token, str(store.id), "txn-adv-refund", amount="80.00")
    refund = client.post(
        f"/aris3/pos/advances/{to_refund['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-refund-action",
            "action": "REFUND",
            "refund_method": "CASH",
            "reason": "Cliente solicita devolución",
        },
    )
    assert refund.status_code == 200, refund.text
    assert refund.json()["status"] == "REFUNDED"
    assert refund.json()["refunded_cash_movement_id"] is not None

    movement = (
        db_session.query(PosCashMovement)
        .filter(PosCashMovement.transaction_id == "txn-adv-refund-action")
        .order_by(PosCashMovement.created_at.desc())
        .first()
    )
    assert movement is not None
    assert movement.action == "CASH_OUT"

    refunded_cannot_consume = client.post(
        f"/aris3/pos/advances/{to_refund['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-adv-refund-no-reuse", "action": "CONSUME", "sale_total": "100.00"},
    )
    assert refunded_cannot_consume.status_code == 409

    to_expire = _issue_advance(client, token, str(store.id), "txn-adv-expire", amount="70.00")
    exp_row = db_session.query(PosAdvance).filter(PosAdvance.id == to_expire["id"]).one()
    exp_row.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.add(exp_row)
    db_session.commit()

    auto_expired = client.get(f"/aris3/pos/advances/{to_expire['id']}", headers={"Authorization": f"Bearer {token}"})
    assert auto_expired.status_code == 200
    assert auto_expired.json()["status"] == "EXPIRED"

    expired_cannot_refund = client.post(
        f"/aris3/pos/advances/{to_expire['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-adv-exp-no-refund", "action": "REFUND", "refund_method": "CASH"},
    )
    assert expired_cannot_refund.status_code == 409

    for idx, days_left in enumerate([2, 5, 6], start=1):
        item = _issue_advance(client, token, str(store.id), f"txn-adv-alert-{idx}", amount="60.00")
        row = db_session.query(PosAdvance).filter(PosAdvance.id == item["id"]).one()
        row.expires_at = datetime.utcnow() + timedelta(days=days_left)
        if days_left == 6:
            row.status = "CONSUMED"
        db_session.add(row)
    db_session.commit()

    alerts = client.get(
        "/aris3/pos/advances/alerts",
        headers={"Authorization": f"Bearer {token}"},
        params={"days": 5, "store_id": str(store.id)},
    )
    assert alerts.status_code == 200
    alert_rows = alerts.json()["rows"]
    assert len(alert_rows) == 2
    assert all(row["status"] == "ACTIVE" for row in alert_rows)
    assert all(row["days_to_expiry"] <= 5 for row in alert_rows)

    exact = _issue_advance(client, token, str(store.id), "txn-adv-exact", amount="40.00")
    exact_consume = client.post(
        f"/aris3/pos/advances/{exact['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-adv-exact-consume", "action": "CONSUME", "sale_total": "40.00"},
    )
    assert exact_consume.status_code == 200
    assert Decimal(exact_consume.json()["remaining_amount_to_charge"]) == Decimal("0.00")

    concurrent = _issue_advance(client, token, str(store.id), "txn-adv-concurrent", amount="30.00")

    def _consume_once(idx: int) -> int:
        response = client.post(
            f"/aris3/pos/advances/{concurrent['id']}/actions",
            headers={"Authorization": f"Bearer {token}"},
            json={"transaction_id": f"txn-adv-concurrent-{idx}", "action": "CONSUME", "sale_total": "30.00"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(_consume_once, [1, 2]))

    assert statuses.count(200) == 1
    assert statuses.count(409) == 1
