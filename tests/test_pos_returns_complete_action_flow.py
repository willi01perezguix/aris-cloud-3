from __future__ import annotations

from datetime import datetime, timedelta

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


def _setup_sale_for_returns(client, db_session, *, suffix: str, unit_price: float = 206.0):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix=suffix)
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku=f"SKU-{suffix.upper()}",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=unit_price,
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
        [sale_line(line_type="SKU", qty=1, unit_price=unit_price, sku=f"SKU-{suffix.upper()}", epc=None)],
        payments=[{"method": "CASH", "amount": f"{unit_price:.2f}"}],
        create_txn=f"txn-sale-create-{suffix}",
        checkout_txn=f"txn-sale-checkout-{suffix}",
        idempotency_key=f"idem-sale-create-{suffix}",
        checkout_idempotency_key=f"idem-sale-checkout-{suffix}",
    )
    return token, sale


def _draft_return(client, token: str, sale: dict, *, suffix: str):
    line_id = sale["lines"][0]["id"]
    quote_payload = {
        "transaction_id": f"txn-return-quote-{suffix}",
        "store_id": sale["header"]["store_id"],
        "sale_id": sale["header"]["id"],
        "items": [{"sale_line_id": line_id, "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
    }
    quote_response = client.post("/aris3/pos/returns/quote", headers={"Authorization": f"Bearer {token}"}, json=quote_payload)
    assert quote_response.status_code == 200

    create_payload = {
        "transaction_id": f"txn-return-create-{suffix}",
        "store_id": sale["header"]["store_id"],
        "sale_id": sale["header"]["id"],
        "items": [{"sale_line_id": line_id, "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
    }
    create_response = client.post("/aris3/pos/returns", headers={"Authorization": f"Bearer {token}"}, json=create_payload)
    assert create_response.status_code == 201
    return quote_response.json(), create_response.json()


def test_pos_returns_complete_persists_transition_and_sale_aggregates(client, db_session):
    token, sale = _setup_sale_for_returns(client, db_session, suffix="complete-flow")

    eligibility = client.get(
        f"/aris3/pos/returns/eligibility?sale_id={sale['header']['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert eligibility.status_code == 200
    assert eligibility.json()["eligible"] is True
    assert len(eligibility.json()["lines"]) == 1

    quote, draft = _draft_return(client, token, sale, suffix="complete-flow")
    assert quote["refund_total"] == "206.00"
    assert quote["exchange_total"] == "0.00"
    assert quote["net_adjustment"] == "-206.00"
    assert quote["settlement_direction"] == "STORE_REFUNDS"

    assert draft["status"] == "DRAFT"
    assert draft["refund_total"] == "206.00"
    assert draft["settlement_direction"] == "STORE_REFUNDS"

    complete_response = client.post(
        f"/aris3/pos/returns/{draft['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-return-complete-complete-flow",
            "action": "COMPLETE",
            "settlement_payments": [{"method": "CASH", "amount": "206.00"}],
        },
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["status"] == "COMPLETED"
    assert completed["completed_at"] is not None
    assert completed["settlement_payments"] == [{"method": "CASH", "amount": "206.00", "authorization_code": None, "bank_name": None, "voucher_number": None}]
    assert [event["action"] for event in completed["events"]] == ["CREATED", "COMPLETE"]

    detail_after = client.get(f"/aris3/pos/returns/{draft['id']}", headers={"Authorization": f"Bearer {token}"})
    assert detail_after.status_code == 200
    assert detail_after.json()["status"] == "COMPLETED"
    assert detail_after.json()["settlement_payments"] == completed["settlement_payments"]

    sale_detail = client.get(f"/aris3/pos/sales/{sale['header']['id']}", headers={"Authorization": f"Bearer {token}"})
    assert sale_detail.status_code == 200
    sale_json = sale_detail.json()
    assert sale_json["refunded_totals"]["total"] == "206.00"
    assert sale_json["exchanged_totals"]["total"] == "0.00"
    assert sale_json["net_adjustment"] == "-206.00"
    assert len(sale_json["return_events"]) == 1


def test_pos_returns_void_stays_voided_and_does_not_apply_sale_aggregates(client, db_session):
    token, sale = _setup_sale_for_returns(client, db_session, suffix="void-flow", unit_price=50.0)
    _quote, draft = _draft_return(client, token, sale, suffix="void-flow")

    void_response = client.post(
        f"/aris3/pos/returns/{draft['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"transaction_id": "txn-return-void-void-flow", "action": "VOID", "reason": "operator canceled"},
    )
    assert void_response.status_code == 200
    payload = void_response.json()
    assert payload["status"] == "VOIDED"
    assert payload["completed_at"] is None
    assert payload["settlement_payments"] == []
    assert [event["action"] for event in payload["events"]] == ["CREATED", "VOID"]

    sale_detail = client.get(f"/aris3/pos/sales/{sale['header']['id']}", headers={"Authorization": f"Bearer {token}"})
    assert sale_detail.status_code == 200
    sale_json = sale_detail.json()
    assert sale_json["refunded_totals"]["total"] == "0.00"
    assert sale_json["exchanged_totals"]["total"] == "0.00"
    assert sale_json["net_adjustment"] == "0.00"
    assert sale_json["return_events"] == []


def test_pos_returns_invalid_state_transition_returns_409(client, db_session):
    token, sale = _setup_sale_for_returns(client, db_session, suffix="invalid-transition", unit_price=25.0)
    _quote, draft = _draft_return(client, token, sale, suffix="invalid-transition")

    complete_response = client.post(
        f"/aris3/pos/returns/{draft['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-return-complete-invalid-transition-1",
            "action": "COMPLETE",
            "settlement_payments": [{"method": "CASH", "amount": "25.00"}],
        },
    )
    assert complete_response.status_code == 200

    second_complete = client.post(
        f"/aris3/pos/returns/{draft['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-return-complete-invalid-transition-2",
            "action": "COMPLETE",
            "settlement_payments": [{"method": "CASH", "amount": "25.00"}],
        },
    )
    assert second_complete.status_code == 409
    assert second_complete.json()["code"] == "BUSINESS_CONFLICT"


def test_pos_returns_quote_fails_when_sale_is_outside_7_day_window(client, db_session):
    token, sale = _setup_sale_for_returns(client, db_session, suffix="window-expired", unit_price=20.0)
    sale_row = db_session.query(PosSale).filter(PosSale.id == sale["header"]["id"]).first()
    assert sale_row is not None
    sale_row.checked_out_at = datetime.utcnow() - timedelta(days=8)
    db_session.add(sale_row)
    db_session.commit()

    response = client.post(
        "/aris3/pos/returns/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-return-quote-window-expired",
            "store_id": sale["header"]["store_id"],
            "sale_id": sale["header"]["id"],
            "items": [{"sale_line_id": sale["lines"][0]["id"], "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
        },
    )
    assert response.status_code == 409
    assert response.json()["details"]["message"] == "exchange window expired"
