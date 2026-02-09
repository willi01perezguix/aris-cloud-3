import uuid

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import User
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def test_returns_cross_tenant_denied(client, db_session):
    seed_defaults(db_session)
    tenant1, store1, _other_store1, user1 = create_tenant_user(db_session, suffix="returns-tenant1")
    tenant2, _store2, _other_store2, user2 = create_tenant_user(db_session, suffix="returns-tenant2")

    token1 = login(client, user1.username, "Pass1234!")
    token2 = login(client, user2.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant1.id),
        sku="SKU-BOUND",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token1,
        str(store1.id),
        [sale_line(line_type="SKU", qty=1, unit_price=6.0, sku="SKU-BOUND", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 6, "authorization_code": "AUTH-B1"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token1,
        {"allow_refund_card": True, "require_receipt": False, "accepted_conditions": ["NEW"]},
        idempotency_key="return-policy-tenant1",
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token2}", "Idempotency-Key": "refund-cross-tenant"},
        json={
            "transaction_id": "txn-bound-1",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CARD", "amount": 6, "authorization_code": "AUTH-B2"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.CROSS_TENANT_ACCESS_DENIED.code


def test_returns_store_scope_and_rbac_denied(client, db_session):
    seed_defaults(db_session)
    tenant, store, other_store, admin_user = create_tenant_user(db_session, suffix="returns-scope")
    token_admin = login(client, admin_user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-SCOPE",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token_admin,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=7.0, sku="SKU-SCOPE", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 7, "authorization_code": "AUTH-SCOPE"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token_admin,
        {"allow_refund_card": True, "require_receipt": False, "accepted_conditions": ["NEW"]},
        idempotency_key="return-policy-scope",
    )

    store_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=other_store.id,
        username="store-user",
        email="store-user@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="MANAGER",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    same_store_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username="same-store-user",
        email="same-store-user@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="USER",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([store_user, same_store_user])
    db_session.commit()

    token_store_user = login(client, store_user.username, "Pass1234!")
    token_same_store = login(client, same_store_user.username, "Pass1234!")

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token_store_user}", "Idempotency-Key": "refund-store-scope"},
        json={
            "transaction_id": "txn-bound-2",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CARD", "amount": 7, "authorization_code": "AUTH-SCOPE-2"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.STORE_SCOPE_MISMATCH.code

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token_same_store}", "Idempotency-Key": "refund-rbac-denied"},
        json={
            "transaction_id": "txn-bound-3",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CARD", "amount": 7, "authorization_code": "AUTH-SCOPE-3"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code
