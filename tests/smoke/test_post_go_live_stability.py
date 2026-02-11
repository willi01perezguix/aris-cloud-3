from __future__ import annotations

import uuid
from datetime import date, datetime

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed
from tests.pos_sales_helpers import create_stock_item, open_cash_session, sale_line


def _create_user(db_session, *, tenant, store, username: str, role: str = "ADMIN", password: str = "Pass1234!") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(password),
        role=role,
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _login(client, username: str, password: str = "Pass1234!") -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _seed_tenant_context(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    origin = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix} A")
    destination = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix} B")
    db_session.add_all([tenant, origin, destination])
    db_session.commit()
    return tenant, origin, destination


def test_post_go_live_auth_and_me(client, db_session):
    run_seed(db_session)
    tenant, store, _ = _seed_tenant_context(db_session, suffix="auth")
    user = _create_user(db_session, tenant=tenant, store=store, username="s6d8-auth")

    token = _login(client, user.username)
    me = client.get("/aris3/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["tenant_id"] == str(tenant.id)


def test_post_go_live_stock_contract_and_totals_invariant(client, db_session):
    run_seed(db_session)
    tenant, store, _ = _seed_tenant_context(db_session, suffix="stock")
    user = _create_user(db_session, tenant=tenant, store=store, username="s6d8-stock")

    db_session.add_all(
        [
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-S6D8", epc="S" * 24, status="RFID", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-S6D8", epc=None, status="PENDING", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-S6D8", epc=None, status="IN_TRANSIT", location_is_vendible=False),
        ]
    )
    db_session.commit()

    token = _login(client, user.username)
    response = client.get("/aris3/stock", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"meta", "rows", "totals"}
    assert payload["totals"]["total_units"] == payload["totals"]["total_rfid"] + payload["totals"]["total_pending"]


def test_post_go_live_transfer_action_happy_path(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store = _seed_tenant_context(db_session, suffix="transfer")
    origin_user = _create_user(db_session, tenant=tenant, store=origin_store, username="s6d8-transfer-origin")
    destination_user = _create_user(db_session, tenant=tenant, store=destination_store, username="s6d8-transfer-dest")

    epc = "T" * 24
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku="SKU-S6D8-TR",
            epc=epc,
            status="RFID",
            location_code="ORIG-1",
            pool="P1",
            location_is_vendible=True,
        )
    )
    db_session.commit()

    origin_token = _login(client, origin_user.username)
    destination_token = _login(client, destination_user.username)

    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "s6d8-transfer-create"},
        json={
            "transaction_id": "txn-s6d8-transfer-create",
            "origin_store_id": str(origin_store.id),
            "destination_store_id": str(destination_store.id),
            "lines": [
                {
                    "line_type": "EPC",
                    "qty": 1,
                    "snapshot": {
                        "sku": "SKU-S6D8-TR",
                        "description": "Post go-live transfer line",
                        "var1_value": "Blue",
                        "var2_value": "L",
                        "epc": epc,
                        "location_code": "ORIG-1",
                        "pool": "P1",
                        "status": "RFID",
                        "location_is_vendible": True,
                        "image_asset_id": str(uuid.uuid4()),
                        "image_url": "https://example.com/image.png",
                        "image_thumb_url": "https://example.com/thumb.png",
                        "image_source": "catalog",
                        "image_updated_at": datetime.utcnow().isoformat(),
                    },
                }
            ],
        },
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]
    line_id = create_response.json()["lines"][0]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "s6d8-transfer-dispatch"},
        json={"transaction_id": "txn-s6d8-transfer-dispatch", "action": "dispatch"},
    )
    assert dispatch.status_code == 200

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "s6d8-transfer-receive"},
        json={
            "transaction_id": "txn-s6d8-transfer-receive",
            "action": "receive",
            "receive_lines": [
                {
                    "line_id": line_id,
                    "qty": 1,
                    "location_code": "DEST-1",
                    "pool": "DP1",
                    "location_is_vendible": True,
                }
            ],
        },
    )
    assert receive.status_code == 200
    assert receive.json()["header"]["status"] == "RECEIVED"


def test_post_go_live_pos_checkout_with_cash_session_and_reports(client, db_session):
    run_seed(db_session)
    tenant, store, _ = _seed_tenant_context(db_session, suffix="pos")
    user = _create_user(db_session, tenant=tenant, store=store, username="s6d8-pos")
    token = _login(client, user.username)

    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-S6D8-POS", epc=None, location_code="LOC-1", pool="P1", status="PENDING")
    sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "s6d8-sale-create"},
        json={
            "transaction_id": "txn-s6d8-sale-create",
            "store_id": str(store.id),
            "lines": [sale_line(line_type="SKU", qty=1, unit_price=25.0, sku="SKU-S6D8-POS", epc=None, status="PENDING")],
        },
    )
    assert sale.status_code == 201
    sale_id = sale.json()["header"]["id"]

    checkout_without_cash = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "s6d8-checkout-no-cash"},
        json={"transaction_id": "txn-s6d8-checkout-no-cash", "action": "checkout", "payments": [{"method": "CASH", "amount": 25.0}]},
    )
    assert checkout_without_cash.status_code == 422

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-S6D8-POS", epc=None, location_code="LOC-1", pool="P1", status="PENDING")

    sale2 = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "s6d8-sale-create-2"},
        json={
            "transaction_id": "txn-s6d8-sale-create-2",
            "store_id": str(store.id),
            "lines": [sale_line(line_type="SKU", qty=1, unit_price=25.0, sku="SKU-S6D8-POS", epc=None, status="PENDING")],
        },
    )
    assert sale2.status_code == 201
    sale2_id = sale2.json()["header"]["id"]

    checkout_with_cash = client.post(
        f"/aris3/pos/sales/{sale2_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "s6d8-checkout-with-cash"},
        json={"transaction_id": "txn-s6d8-checkout-with-cash", "action": "checkout", "payments": [{"method": "CASH", "amount": 25.0}]},
    )
    assert checkout_with_cash.status_code == 200

    today = date.today().isoformat()
    overview = client.get(
        "/aris3/reports/overview",
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert overview.status_code == 200

    exports_list = client.get("/aris3/exports", headers={"Authorization": f"Bearer {token}"})
    assert exports_list.status_code == 200


def test_post_go_live_unauthorized_protected_action_blocked(client, db_session):
    run_seed(db_session)
    tenant, store, _ = _seed_tenant_context(db_session, suffix="rbac")
    user = _create_user(db_session, tenant=tenant, store=store, username="s6d8-rbac", role="USER")

    token = _login(client, user.username)
    forbidden = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "s6d8-rbac-forbidden"},
        json={"transaction_id": "txn-s6d8-rbac-forbidden", "variant_fields": [{"key": "material", "label": "Material"}]},
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "PERMISSION_DENIED"
