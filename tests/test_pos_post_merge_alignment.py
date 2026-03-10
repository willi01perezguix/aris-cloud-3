from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.aris3.db.models import PosCashMovement
from app.aris3.db.seed import run_seed
from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    set_return_policy,
)


def test_pos_cash_session_actions_end_to_end_http_contract(client, db_session):
    run_seed(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-http")
    token = login(client, user.username, "Pass1234!")

    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-open-http"}
    open_response = client.post(
        "/aris3/pos/cash/session/actions",
        headers=headers,
        json={
            "transaction_id": "txn-cash-open-http",
            "tenant_id": str(tenant.id),
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 100,
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
            "reason": "Shift start",
        },
    )
    assert open_response.status_code == 200

    cash_in = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-in-http"},
        json={
            "transaction_id": "txn-cash-in-http",
            "tenant_id": str(tenant.id),
            "store_id": str(store.id),
            "action": "CASH_IN",
            "amount": 50,
            "reason": "Float",
        },
    )
    assert cash_in.status_code == 200

    cash_out = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-out-http"},
        json={
            "transaction_id": "txn-cash-out-http",
            "tenant_id": str(tenant.id),
            "store_id": str(store.id),
            "action": "CASH_OUT",
            "amount": 20,
            "reason": "Petty cash",
        },
    )
    assert cash_out.status_code == 200

    close = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-close-http"},
        json={
            "transaction_id": "txn-cash-close-http",
            "tenant_id": str(tenant.id),
            "store_id": str(store.id),
            "action": "CLOSE",
            "counted_cash": 130,
            "reason": "Shift end",
        },
    )
    assert close.status_code == 200

    day_close = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-day-close-http"},
        json={
            "transaction_id": "txn-day-close-http",
            "tenant_id": str(tenant.id),
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
            "reason": "End of day",
        },
    )
    assert day_close.status_code == 200


def test_pos_sales_prevents_cross_store_stock_leakage(client, db_session):
    run_seed(db_session)
    tenant, store_a, store_b, user = create_tenant_user(db_session, suffix="store-scope")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store_b.id),
        sku="SKU-CROSS-STORE",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=10.0,
    )

    create_response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cross-store-create"},
        json=sale_payload(str(store_a.id), [sale_line(line_type="SKU", qty=1, sku="SKU-CROSS-STORE", epc=None)], transaction_id="txn-cross-store"),
    )
    assert create_response.status_code == 422


def test_checkout_cash_movement_uses_net_cash_after_change(client, db_session):
    run_seed(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-net")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        sku="SKU-CASH-NET",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=10.0,
    )

    sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-net-create"},
        json=sale_payload(str(store.id), [sale_line(line_type="SKU", qty=1, sku="SKU-CASH-NET", epc=None)], transaction_id="txn-cash-net-create"),
    )
    assert sale.status_code == 201
    sale_id = sale.json()["header"]["id"]

    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-net-checkout"},
        json={"transaction_id": "txn-cash-net-checkout", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": 20}]},
    )
    assert checkout.status_code == 200
    assert checkout.json()["header"]["change_due"] == "10.00"

    movement = db_session.query(PosCashMovement).filter(PosCashMovement.sale_id == sale_id).order_by(PosCashMovement.created_at.desc()).first()
    assert movement is not None
    assert Decimal(str(movement.amount)) == Decimal("10.00")


def test_exchange_canonical_lines_and_net_cash_movement(client, db_session):
    run_seed(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exchange-canon")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    create_stock_item(db_session, tenant_id=str(tenant.id), store_id=str(store.id), sku="SKU-OLD", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=20.0)
    create_stock_item(db_session, tenant_id=str(tenant.id), store_id=str(store.id), sku="SKU-NEW", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=30.0)

    sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-sale-create"},
        json=sale_payload(str(store.id), [sale_line(line_type="SKU", qty=1, sku="SKU-OLD", epc=None)], transaction_id="txn-exchange-create"),
    )
    assert sale.status_code == 201
    sale_id = sale.json()["header"]["id"]

    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-sale-checkout"},
        json={"transaction_id": "txn-exchange-checkout", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": 20}]},
    )
    assert checkout.status_code == 200

    set_return_policy(
        client,
        token,
        {
            "allow_returns": True,
            "allow_exchange": True,
            "require_receipt": False,
            "return_window_days": 30,
            "restocking_fee_pct": 0,
            "allow_refund_cash": True,
            "allow_refund_card": True,
            "allow_refund_transfer": True,
            "accepted_conditions": ["GOOD"],
            "manager_override_roles": ["ADMIN"],
        },
        idempotency_key="exchange-policy",
    )

    exchange = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-action"},
        json={
            "transaction_id": "txn-exchange-action",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": checkout.json()["lines"][0]["id"], "qty": 1, "condition": "GOOD"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-NEW", "qty": 1}],
            "payments": [{"method": "CASH", "amount": 15}],
        },
    )
    assert exchange.status_code == 200

    event = db_session.query(PosCashMovement).filter(PosCashMovement.sale_id == sale_id).order_by(PosCashMovement.created_at.desc()).first()
    assert event is not None
    assert Decimal(str(event.amount)) == Decimal("10.00")
