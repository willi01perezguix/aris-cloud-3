from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    sale_payload,
    seed_defaults,
)


def test_post_close_guardrails_block_mutations(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, manager = create_tenant_user(
        db_session, suffix="pos-cash-post-close", role="MANAGER"
    )
    token = login(client, manager.username, "Pass1234!")
    business_date = date.today()

    open_session = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "post-open"},
        json={
            "transaction_id": "txn-post-open",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 60.0,
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert open_session.status_code == 200

    force_close = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "post-day-close"},
        json={
            "transaction_id": "txn-post-day-close",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
            "force_if_open_sessions": True,
            "reason": "End of day lock",
        },
    )
    assert force_close.status_code == 200

    blocked_cash_in = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "post-cash-in"},
        json={
            "transaction_id": "txn-post-cash-in",
            "store_id": str(store.id),
            "action": "CASH_IN",
            "amount": 5.0,
        },
    )
    assert blocked_cash_in.status_code == 422
    assert blocked_cash_in.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-POST",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    create_sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "post-sale-create"},
        json=sale_payload(
            str(store.id),
            [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-POST", epc=None, status="PENDING")],
            transaction_id="txn-post-sale-create",
        ),
    )
    assert create_sale.status_code == 201
    sale_id = create_sale.json()["header"]["id"]

    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "post-sale-checkout"},
        json={
            "transaction_id": "txn-post-sale-checkout",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert checkout.status_code == 422
    assert checkout.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
