from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def _refund_payload(line_id: str, *, transaction_id: str, receipt_number: str | None, condition: str = "NEW"):
    return {
        "transaction_id": transaction_id,
        "action": "REFUND_ITEMS",
        "receipt_number": receipt_number,
        "return_items": [{"line_id": line_id, "qty": 1, "condition": condition}],
        "refund_payments": [{"method": "CARD", "amount": 10, "authorization_code": "AUTH-1"}],
    }


def test_refund_policy_receipt_and_condition_enforced(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="refund-policy-1")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(_tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-1", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 10, "authorization_code": "AUTH-1"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token,
        {
            "require_receipt": True,
            "accepted_conditions": ["NEW"],
            "allow_refund_card": True,
            "allow_refund_cash": False,
            "allow_refund_transfer": False,
            "require_manager_for_exceptions": False,
        },
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-missing-receipt"},
        json=_refund_payload(line_id, transaction_id="txn-refund-1", receipt_number=None),
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-condition"},
        json=_refund_payload(line_id, transaction_id="txn-refund-2", receipt_number="RCPT-1", condition="DAMAGED"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_refund_policy_manager_override_gate(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="refund-policy-2")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-2",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-2", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 10, "authorization_code": "AUTH-1"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token,
        {
            "return_window_days": 0,
            "require_receipt": True,
            "accepted_conditions": ["NEW"],
            "allow_refund_card": True,
            "require_manager_for_exceptions": True,
        },
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-no-override"},
        json=_refund_payload(line_id, transaction_id="txn-refund-3", receipt_number="RCPT-2"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    db_session.refresh(user)
    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-with-override"},
        json={
            **_refund_payload(line_id, transaction_id="txn-refund-4", receipt_number="RCPT-3"),
            "manager_override": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["refunded_totals"]["total"] == "10.00"
