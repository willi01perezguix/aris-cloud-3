from datetime import date, datetime
import uuid

from app.aris3.db.models import PosCashMovement, PosCashSession
from tests.pos_sales_helpers import create_paid_sale, create_stock_item, create_tenant_user, login, sale_line, seed_defaults


def _open_session(client, token: str, store_id: str, *, opening_amount: float = 100.0):
    response = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"ik-open-{store_id}"},
        json={
            "transaction_id": f"txn-open-{store_id}",
            "store_id": store_id,
            "action": "OPEN",
            "opening_amount": opening_amount,
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
        },
    )
    assert response.status_code == 200


def _new_paid_sale(client, db_session, token: str, tenant_id: str, store_id: str, sku: str, payments: list[dict], *, idx: str):
    create_stock_item(
        db_session,
        tenant_id=tenant_id,
        store_id=store_id,
        sku=sku,
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="RFID",
        sale_price=25.0,
    )
    return create_paid_sale(
        client,
        token,
        store_id,
        [sale_line(line_type="SKU", qty=1, unit_price=25.0, sku=sku, epc=None)],
        payments,
        create_txn=f"txn-sale-create-{idx}",
        checkout_txn=f"txn-sale-checkout-{idx}",
        idempotency_key=f"ik-sale-create-{idx}",
        checkout_idempotency_key=f"ik-sale-checkout-{idx}",
        receipt_number=f"RCPT-{idx}",
    )


def test_cash_cut_quote_and_create_keep_session_open_and_math(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-cut-main")
    token = login(client, user.username, "Pass1234!")

    _open_session(client, token, str(store.id), opening_amount=100.0)

    _new_paid_sale(
        client,
        db_session,
        token,
        str(tenant.id),
        str(store.id),
        "SKU-CUT-CASH",
        [{"method": "CASH", "amount": "25.00"}],
        idx="cash",
    )
    _new_paid_sale(
        client,
        db_session,
        token,
        str(tenant.id),
        str(store.id),
        "SKU-CUT-CARD",
        [{"method": "CARD", "amount": "25.00", "authorization_code": "AUTH-1"}],
        idx="card",
    )
    sale_mixed = _new_paid_sale(
        client,
        db_session,
        token,
        str(tenant.id),
        str(store.id),
        "SKU-CUT-MIX",
        [
            {"method": "CASH", "amount": "5.00"},
            {"method": "CARD", "amount": "20.00", "authorization_code": "AUTH-2"},
        ],
        idx="mixed",
    )

    cash_in = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-cut-cash-in"},
        json={"transaction_id": "txn-cut-cash-in", "store_id": str(store.id), "action": "CASH_IN", "amount": 10.0},
    )
    assert cash_in.status_code == 200

    cash_out = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-cut-cash-out"},
        json={"transaction_id": "txn-cut-cash-out", "store_id": str(store.id), "action": "CASH_OUT", "amount": 5.0},
    )
    assert cash_out.status_code == 200

    session = db_session.query(PosCashSession).filter(PosCashSession.store_id == str(store.id)).first()
    db_session.add(
        PosCashMovement(
            id=uuid.uuid4(),
            tenant_id=str(tenant.id),
            store_id=str(store.id),
            cash_session_id=session.id,
            cashier_user_id=str(user.id),
            actor_user_id=str(user.id),
            business_date=date.today(),
            timezone="UTC",
            sale_id=None,
            action="CASH_OUT_REFUND",
            amount=8.0,
            expected_balance_before=None,
            expected_balance_after=None,
            transaction_id="txn-cut-refund",
            reason="test refund movement",
            trace_id=None,
            occurred_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    quote = client.post(
        "/aris3/pos/cash/cuts/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={"store_id": str(store.id), "use_last_cut_window": False, "cut_type": "PARTIAL"},
    )
    assert quote.status_code == 200
    q = quote.json()["quote"]
    assert q["cash_sales_total"] == "30.00"
    assert q["card_sales_total"] == "45.00"
    assert q["mixed_cash_component_total"] == "5.00"
    assert q["mixed_card_component_total"] == "20.00"
    assert q["cash_in_total"] == "10.00"
    assert q["cash_out_total"] == "5.00"
    assert q["cash_refunds_total"] == "8.00"
    assert q["expected_cash"] == "127.00"

    create = client.post(
        "/aris3/pos/cash/cuts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-cut-create",
            "store_id": str(store.id),
            "use_last_cut_window": False,
            "counted_cash": "126.00",
            "deposit_removed_amount": "10.00",
            "auto_apply_cash_out": True,
            "notes": "bank pickup",
        },
    )
    assert create.status_code == 200
    cut = create.json()["cut"]
    assert cut["difference"] == "-1.00"
    assert cut["deposit_cash_movement_id"] is not None

    session_current = client.get(
        "/aris3/pos/cash/session/current",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id)},
    )
    assert session_current.status_code == 200
    assert session_current.json()["session"]["status"] == "OPEN"

    movement = db_session.query(PosCashMovement).filter(PosCashMovement.transaction_id == "txn-cut-create-cut-deposit").first()
    assert movement is not None
    assert movement.action == "CASH_OUT"
    assert movement.amount == 10.0


def test_cash_cut_after_prior_cut_uses_last_window(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-cut-window")
    token = login(client, user.username, "Pass1234!")
    _open_session(client, token, str(store.id), opening_amount=50.0)

    first_cut = client.post(
        "/aris3/pos/cash/cuts",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-cut-first", "store_id": str(store.id), "use_last_cut_window": False},
    )
    assert first_cut.status_code == 200

    cash_in = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-cut-window-cash-in"},
        json={"transaction_id": "txn-cut-window-cash-in", "store_id": str(store.id), "action": "CASH_IN", "amount": 7.0},
    )
    assert cash_in.status_code == 200

    quote = client.post(
        "/aris3/pos/cash/cuts/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={"store_id": str(store.id), "use_last_cut_window": True},
    )
    assert quote.status_code == 200
    assert quote.json()["quote"]["opening_amount_snapshot"] == "50.00"
    assert quote.json()["quote"]["cash_in_total"] == "7.00"


def test_cash_cut_requires_open_session_and_store_scope(client, db_session):
    seed_defaults(db_session)
    tenant, store, other_store, user = create_tenant_user(db_session, suffix="cash-cut-scope")
    token = login(client, user.username, "Pass1234!")

    no_session = client.post(
        "/aris3/pos/cash/cuts/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={"store_id": str(store.id)},
    )
    assert no_session.status_code == 409

    _open_session(client, token, str(store.id))
    cut = client.post(
        "/aris3/pos/cash/cuts",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-cut-scope", "store_id": str(store.id), "use_last_cut_window": False},
    )
    assert cut.status_code == 200
    cut_id = cut.json()["cut"]["id"]

    leaked = client.get(
        f"/aris3/pos/cash/cuts/{cut_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(other_store.id)},
    )
    assert leaked.status_code in (403, 404)


def test_cash_cut_complete_persists_counted_cash_difference_and_notes(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-cut-complete")
    token = login(client, user.username, "Pass1234!")
    _open_session(client, token, str(store.id), opening_amount=100.0)

    create = client.post(
        "/aris3/pos/cash/cuts",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-cut-complete-create", "store_id": str(store.id), "use_last_cut_window": False},
    )
    assert create.status_code == 200
    cut = create.json()["cut"]
    cut_id = cut["id"]
    assert cut["status"] == "OPEN"
    assert cut["counted_cash"] is None
    assert cut["difference"] is None

    complete = client.post(
        f"/aris3/pos/cash/cuts/{cut_id}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-cut-complete-action",
            "store_id": str(store.id),
            "action": "COMPLETE",
            "counted_cash": "98.00",
            "notes": "partial cut test",
        },
    )
    assert complete.status_code == 200
    completed_cut = complete.json()["cut"]
    assert completed_cut["status"] == "COMPLETED"
    assert completed_cut["counted_cash"] == "98.00"
    assert completed_cut["difference"] == "-2.00"
    assert completed_cut["notes"] == "partial cut test"
    assert completed_cut["completed_at"] is not None

    detail = client.get(
        f"/aris3/pos/cash/cuts/{cut_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id)},
    )
    assert detail.status_code == 200
    detailed_cut = detail.json()["cut"]
    assert detailed_cut["status"] == "COMPLETED"
    assert detailed_cut["counted_cash"] == "98.00"
    assert detailed_cut["difference"] == "-2.00"
    assert detailed_cut["notes"] == "partial cut test"


def test_cash_cut_complete_requires_counted_cash(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-cut-complete-validation")
    token = login(client, user.username, "Pass1234!")
    _open_session(client, token, str(store.id), opening_amount=100.0)

    create = client.post(
        "/aris3/pos/cash/cuts",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-cut-complete-validation-create", "store_id": str(store.id), "use_last_cut_window": False},
    )
    assert create.status_code == 200
    cut_id = create.json()["cut"]["id"]

    complete = client.post(
        f"/aris3/pos/cash/cuts/{cut_id}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-cut-complete-validation-action",
            "store_id": str(store.id),
            "action": "COMPLETE",
            "notes": "missing counted cash",
        },
    )
    assert complete.status_code == 422
    assert complete.json()["details"]["message"] == "counted_cash is required"


def test_cash_cut_void_keeps_completion_fields_unchanged(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-cut-void")
    token = login(client, user.username, "Pass1234!")
    _open_session(client, token, str(store.id), opening_amount=100.0)

    create = client.post(
        "/aris3/pos/cash/cuts",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-cut-void-create", "store_id": str(store.id), "use_last_cut_window": False},
    )
    assert create.status_code == 200
    cut_id = create.json()["cut"]["id"]

    void = client.post(
        f"/aris3/pos/cash/cuts/{cut_id}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-cut-void-action",
            "store_id": str(store.id),
            "action": "VOID",
        },
    )
    assert void.status_code == 200
    void_cut = void.json()["cut"]
    assert void_cut["status"] == "VOID"
    assert void_cut["counted_cash"] is None
    assert void_cut["difference"] is None
    assert void_cut["notes"] is None
