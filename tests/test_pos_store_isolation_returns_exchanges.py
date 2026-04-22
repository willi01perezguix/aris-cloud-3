from __future__ import annotations

import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import User
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


def _seed_paid_sale(client, db_session, token: str, *, tenant_id: str, store_id: str, user_id: str, sku: str, price: float, suffix: str):
    create_stock_item(
        db_session,
        tenant_id=tenant_id,
        store_id=store_id,
        sku=sku,
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=price,
    )
    open_cash_session(db_session, tenant_id=tenant_id, store_id=store_id, cashier_user_id=user_id)
    return create_paid_sale(
        client,
        token,
        store_id,
        [sale_line(line_type="SKU", qty=1, unit_price=price, sku=sku, epc=None)],
        payments=[{"method": "CASH", "amount": f"{price:.2f}"}],
        create_txn=f"txn-store-iso-create-{suffix}",
        checkout_txn=f"txn-store-iso-checkout-{suffix}",
        idempotency_key=f"ik-store-iso-create-{suffix}",
        checkout_idempotency_key=f"ik-store-iso-checkout-{suffix}",
    )


def _create_same_tenant_admin(db_session, *, tenant_id: str, store_id: str, suffix: str):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        username=f"admin-{suffix}",
        email=f"admin-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="ACTIVE",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_pos_returns_and_sales_are_store_isolated(client, db_session):
    seed_defaults(db_session)
    tenant, store_a, store_b, admin_a = create_tenant_user(db_session, suffix="pos-store-iso", role="ADMIN")
    token_a = login(client, admin_a.username, "Pass1234!")
    admin_b = _create_same_tenant_admin(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store_b.id),
        suffix="pos-store-iso-b",
    )
    token_b = login(client, admin_b.username, "Pass1234!")

    sale_a = _seed_paid_sale(
        client,
        db_session,
        token_a,
        tenant_id=str(tenant.id),
        store_id=str(store_a.id),
        user_id=str(admin_a.id),
        sku="SKU-ISO-A",
        price=100.0,
        suffix="a",
    )
    sale_b = _seed_paid_sale(
        client,
        db_session,
        token_b,
        tenant_id=str(tenant.id),
        store_id=str(store_b.id),
        user_id=str(admin_b.id),
        sku="SKU-ISO-B",
        price=60.0,
        suffix="b",
    )
    set_return_policy(
        client,
        token_a,
        {
            "allow_exchange": True,
            "require_receipt": False,
            "allow_refund_cash": True,
            "allow_refund_card": True,
            "allow_refund_transfer": True,
            "restocking_fee_pct": "0.00",
            "return_window_days": 7,
            "accepted_conditions": ["NEW", "OPEN_BOX", "DEFECTIVE"],
            "manager_override_enabled": True,
            "non_reusable_label_strategy": "ASSIGN_NEW_EPC",
        },
        idempotency_key="ik-store-iso-return-policy",
    )

    # A/B/I: list endpoint isolates by explicit store_id for broad ADMIN user.
    list_a = client.get("/aris3/pos/sales", headers={"Authorization": f"Bearer {token_a}"}, params={"store_id": str(store_a.id)})
    assert list_a.status_code == 200
    assert {row["id"] for row in list_a.json()["rows"]} == {sale_a["header"]["id"]}

    list_b = client.get("/aris3/pos/sales", headers={"Authorization": f"Bearer {token_a}"}, params={"store_id": str(store_b.id)})
    assert list_b.status_code == 200
    assert {row["id"] for row in list_b.json()["rows"]} == {sale_b["header"]["id"]}

    # J: omitting store_id defaults to token store_id, never all stores.
    list_default = client.get("/aris3/pos/sales", headers={"Authorization": f"Bearer {token_a}"})
    assert list_default.status_code == 200
    assert {row["id"] for row in list_default.json()["rows"]} == {sale_a["header"]["id"]}

    line_a_id = sale_a["lines"][0]["id"]

    # C: eligibility fails when sale belongs to different resolved store.
    eligibility_cross = client.get(
        "/aris3/pos/returns/eligibility",
        headers={"Authorization": f"Bearer {token_a}"},
        params={"sale_id": sale_a["header"]["id"], "store_id": str(store_b.id)},
    )
    assert eligibility_cross.status_code == 403
    assert eligibility_cross.json()["details"]["message"] == "sale belongs to another store"

    # D: quote fails for cross-store sale access.
    quote_cross = client.post(
        "/aris3/pos/returns/quote",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "transaction_id": "txn-quote-cross-store",
            "store_id": str(store_b.id),
            "sale_id": sale_a["header"]["id"],
            "items": [{"sale_line_id": line_a_id, "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
        },
    )
    assert quote_cross.status_code == 403
    assert quote_cross.json()["details"]["message"] == "sale belongs to another store"

    # E: draft creation fails for cross-store sale access.
    draft_cross = client.post(
        "/aris3/pos/returns",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "transaction_id": "txn-draft-cross-store",
            "store_id": str(store_b.id),
            "sale_id": sale_a["header"]["id"],
            "items": [{"sale_line_id": line_a_id, "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
        },
    )
    assert draft_cross.status_code == 403
    assert draft_cross.json()["details"]["message"] == "sale belongs to another store"

    # F: direct exchange action cannot operate sale from another store.
    action_cross = client.post(
        f"/aris3/pos/sales/{sale_a['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": "ik-exchange-cross-store"},
        json={
            "transaction_id": "txn-exchange-cross-store",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": line_a_id, "qty": 1, "condition": "NEW"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-ISO-A", "qty": 1}],
        },
    )
    assert action_cross.status_code == 403
    assert action_cross.json()["details"]["message"] == "sale belongs to another store"

    # G: replacement item in another store is not accepted.
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store_b.id),
        sku="SKU-B-ONLY",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=30.0,
    )
    replacement_cross = client.post(
        f"/aris3/pos/sales/{sale_a['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "ik-replacement-cross-store"},
        json={
            "transaction_id": "txn-replacement-cross-store",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": line_a_id, "qty": 1, "condition": "NEW"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-B-ONLY", "qty": 1}],
        },
    )
    assert replacement_cross.status_code == 422
    assert replacement_cross.json()["details"]["message"] == "replacement item not available in this store"

    # H: same-store exchange succeeds.
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store_a.id),
        sku="SKU-A-EXCHANGE",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=100.0,
    )
    exchange_ok = client.post(
        f"/aris3/pos/sales/{sale_a['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "ik-exchange-same-store"},
        json={
            "transaction_id": "txn-exchange-same-store",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": line_a_id, "qty": 1, "condition": "NEW"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-A-EXCHANGE", "qty": 1}],
        },
    )
    assert exchange_ok.status_code == 200
    return_events = exchange_ok.json()["return_events"]
    assert any(event["action"] == "EXCHANGE_ITEMS" for event in return_events)
