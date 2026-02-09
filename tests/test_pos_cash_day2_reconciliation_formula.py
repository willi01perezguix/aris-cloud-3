from datetime import date
from decimal import Decimal

from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def test_reconciliation_formula_with_mixed_movements(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, manager = create_tenant_user(
        db_session, suffix="pos-cash-recon", role="ADMIN"
    )
    token = login(client, manager.username, "Pass1234!")

    business_date = date.today()
    open_response = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "recon-open"},
        json={
            "transaction_id": "txn-recon-open",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 100.0,
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert open_response.status_code == 200

    cash_in = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "recon-cash-in"},
        json={
            "transaction_id": "txn-recon-cash-in",
            "store_id": str(store.id),
            "action": "CASH_IN",
            "amount": 25.0,
        },
    )
    assert cash_in.status_code == 200

    cash_out = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "recon-cash-out"},
        json={
            "transaction_id": "txn-recon-cash-out",
            "store_id": str(store.id),
            "action": "CASH_OUT",
            "amount": 10.0,
        },
    )
    assert cash_out.status_code == 200

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-RECON",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=20.0, sku="SKU-RECON", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 20.0}],
        create_txn="txn-recon-sale-create",
        checkout_txn="txn-recon-sale-checkout",
        idempotency_key="recon-sale-create",
        checkout_idempotency_key="recon-sale-checkout",
    )

    set_return_policy(
        client,
        token,
        {
            "allow_refund_cash": True,
            "allow_refund_card": False,
            "allow_refund_transfer": False,
            "accepted_conditions": ["NEW"],
            "require_receipt": False,
        },
        idempotency_key="recon-return-policy",
    )

    refund = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "recon-refund"},
        json={
            "transaction_id": "txn-recon-refund",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": sale["lines"][0]["id"], "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CASH", "amount": 20.0}],
        },
    )
    assert refund.status_code == 200

    close_session = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "recon-close"},
        json={
            "transaction_id": "txn-recon-close",
            "store_id": str(store.id),
            "action": "CLOSE",
            "counted_cash": 115.0,
        },
    )
    assert close_session.status_code == 200

    day_close = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "recon-day-close"},
        json={
            "transaction_id": "txn-recon-day-close",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
            "counted_cash": 115.0,
        },
    )
    assert day_close.status_code == 200
    payload = day_close.json()
    assert Decimal(payload["expected_cash"]) == Decimal("115.00")
    assert payload["difference_type"] == "EVEN"
    assert Decimal(payload["net_cash_movement"]) == Decimal("15.00")
    assert Decimal(payload["net_cash_sales"]) == Decimal("20.00")
    assert Decimal(payload["cash_refunds"]) == Decimal("20.00")

    breakdown = client.get(
        "/aris3/pos/cash/reconciliation/breakdown",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "business_date": business_date.isoformat(), "timezone": "UTC"},
    )
    assert breakdown.status_code == 200
    assert Decimal(breakdown.json()["expected_cash"]) == Decimal("115.00")
