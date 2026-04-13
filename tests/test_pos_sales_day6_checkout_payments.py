import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import PosCashMovement, User
from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def _create_sale(client, token: str, store_id: str, transaction_id: str):
    payload = sale_payload(
        store_id,
        [
            sale_line(
                line_type="SKU",
                qty=2,
                unit_price=5.0,
                sku="SKU-1",
                epc=None,
                status="PENDING",
            )
        ],
        transaction_id=transaction_id,
    )
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"pos-sale-{transaction_id}"},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["header"]["id"]


def _seed_two_units(db_session, tenant_id: str, sku: str = "SKU-1"):
    create_stock_item(
        db_session,
        tenant_id=tenant_id,
        sku=sku,
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=tenant_id,
        sku=sku,
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )


def test_cash_checkout_success(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cash")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_sale(client, token, str(store.id), "txn-cash")
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cash"},
        json={
            "transaction_id": "txn-cash-checkout",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert response.status_code == 200
    assert response.json()["header"]["status"] == "PAID"


def test_card_checkout_requires_authorization(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-card")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale_id = _create_sale(client, token, str(store.id), "txn-card")
    fail_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-card-fail"},
        json={
            "transaction_id": "txn-card-checkout-1",
            "action": "checkout",
            "payments": [{"method": "CARD", "amount": 10.0}],
        },
    )
    assert fail_response.status_code == 422

    ok_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-card-ok"},
        json={
            "transaction_id": "txn-card-checkout-2",
            "action": "checkout",
            "payments": [{"method": "CARD", "amount": 10.0, "authorization_code": "AUTH-1"}],
        },
    )
    assert ok_response.status_code == 200


def test_transfer_checkout_requires_voucher_details(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-transfer")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale_id = _create_sale(client, token, str(store.id), "txn-transfer")
    fail_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-transfer-fail"},
        json={
            "transaction_id": "txn-transfer-checkout-1",
            "action": "checkout",
            "payments": [{"method": "TRANSFER", "amount": 10.0}],
        },
    )
    assert fail_response.status_code == 422

    ok_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-transfer-ok"},
        json={
            "transaction_id": "txn-transfer-checkout-2",
            "action": "checkout",
            "payments": [
                {
                    "method": "TRANSFER",
                    "amount": 10.0,
                    "bank_name": "Bank",
                    "voucher_number": "V-1",
                }
            ],
        },
    )
    assert ok_response.status_code == 200


def test_mixed_payment_and_change_rules(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-mixed")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_sale(client, token, str(store.id), "txn-mixed")
    ok_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-mixed-ok"},
        json={
            "transaction_id": "txn-mixed-checkout",
            "action": "checkout",
            "payments": [
                {"method": "CARD", "amount": 6.0, "authorization_code": "AUTH-2"},
                {"method": "CASH", "amount": 6.0},
            ],
        },
    )
    assert ok_response.status_code == 200
    assert float(ok_response.json()["header"]["change_due"]) == 2.0

    sale_id = _create_sale(client, token, str(store.id), "txn-insufficient")
    fail_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-insufficient"},
        json={
            "transaction_id": "txn-insufficient-checkout",
            "action": "checkout",
            "payments": [{"method": "CARD", "amount": 5.0, "authorization_code": "AUTH-3"}],
        },
    )
    assert fail_response.status_code == 422

    sale_id = _create_sale(client, token, str(store.id), "txn-change-only-cash")
    fail_change = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-change-fail"},
        json={
            "transaction_id": "txn-change-fail",
            "action": "checkout",
            "payments": [
                {"method": "CARD", "amount": 12.0, "authorization_code": "AUTH-4"},
            ],
        },
    )
    assert fail_change.status_code == 422


def test_cash_checkout_requires_open_cash_session(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cash-required")
    token = login(client, user.username, "Pass1234!")
    _seed_two_units(db_session, str(tenant.id))

    sale_id = _create_sale(client, token, str(store.id), "txn-cash-required")
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cash-required"},
        json={
            "transaction_id": "txn-cash-required-checkout",
            "action": "CHECKOUT",
            "payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert response.status_code == 409
    assert "open cash session required for CASH payments" in response.json()["details"]["message"]


def test_mixed_cash_card_requires_open_cash_session(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-mixed-cash-required")
    token = login(client, user.username, "Pass1234!")
    _seed_two_units(db_session, str(tenant.id))

    sale_id = _create_sale(client, token, str(store.id), "txn-mixed-cash-required")
    blocked = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-mixed-cash-required"},
        json={
            "transaction_id": "txn-mixed-cash-required-checkout",
            "action": "CHECKOUT",
            "payments": [
                {"method": "CASH", "amount": 4.0},
                {"method": "CARD", "amount": 6.0, "authorization_code": "AUTH-MIXED"},
            ],
        },
    )
    assert blocked.status_code == 409

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))
    sale_id = _create_sale(client, token, str(store.id), "txn-mixed-cash-required-open")
    allowed = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-mixed-cash-required-open"},
        json={
            "transaction_id": "txn-mixed-cash-required-open-checkout",
            "action": "CHECKOUT",
            "payments": [
                {"method": "CASH", "amount": 4.0},
                {"method": "CARD", "amount": 6.0, "authorization_code": "AUTH-MIXED-2"},
            ],
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["header"]["change_due"] == "0.00"

    movements = db_session.query(PosCashMovement).filter(PosCashMovement.sale_id == sale_id).all()
    assert len(movements) == 1
    assert float(movements[0].amount) == 4.0


def test_cash_checkout_uses_single_open_store_session_when_cashier_differs(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, opener_user = create_tenant_user(db_session, suffix="pos-cash-fallback")
    cashier_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username="user-pos-cash-fallback-2",
        email="user-pos-cash-fallback-2@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="ACTIVE",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(cashier_user)
    db_session.commit()
    cashier_token = login(client, cashier_user.username, "Pass1234!")
    _seed_two_units(db_session, str(tenant.id))

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(opener_user.id))
    sale_id = _create_sale(client, cashier_token, str(store.id), "txn-cash-fallback")
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {cashier_token}", "Idempotency-Key": "pos-sale-cash-fallback"},
        json={
            "transaction_id": "txn-cash-fallback-checkout",
            "action": "CHECKOUT",
            "payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert response.status_code == 200


def test_mixed_non_cash_checkout_does_not_require_cash_session_or_create_cash_movement(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-mixed-noncash")
    token = login(client, user.username, "Pass1234!")
    _seed_two_units(db_session, str(tenant.id))

    sale_id = _create_sale(client, token, str(store.id), "txn-mixed-noncash")
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-mixed-noncash"},
        json={
            "transaction_id": "txn-mixed-noncash-checkout",
            "action": "CHECKOUT",
            "payments": [
                {"method": "CARD", "amount": 6.0, "authorization_code": "AUTH-NC"},
                {"method": "TRANSFER", "amount": 4.0, "bank_name": "Bank", "voucher_number": "VCH-1"},
            ],
        },
    )
    assert response.status_code == 200
    movements = db_session.query(PosCashMovement).filter(PosCashMovement.sale_id == sale_id).all()
    assert len(movements) == 0
