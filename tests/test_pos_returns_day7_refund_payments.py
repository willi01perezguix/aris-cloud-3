from uuid import UUID

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.db.models import PosCashMovement
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def test_refund_payments_policy_and_cash_movement(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="refund-payments")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-3",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=15.0, sku="SKU-3", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 15, "authorization_code": "AUTH-2"}],
    )
    line_id = sale["lines"][0]["id"]

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
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-card-denied"},
        json={
            "transaction_id": "txn-refund-5",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CARD", "amount": 15, "authorization_code": "AUTH-REF"}],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    open_cash_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-cash-ok"},
        json={
            "transaction_id": "txn-refund-6",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CASH", "amount": 15}],
        },
    )
    assert response.status_code == 200

    movement = (
        db_session.query(PosCashMovement)
        .filter(PosCashMovement.sale_id == UUID(sale["header"]["id"]), PosCashMovement.action == "CASH_OUT_REFUND")
        .first()
    )
    assert movement is not None
