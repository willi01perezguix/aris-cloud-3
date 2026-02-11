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


def _transfer_payload(origin_store_id: str, destination_store_id: str, epc: str):
    return {
        "transaction_id": "txn-smoke-transfer-create",
        "origin_store_id": origin_store_id,
        "destination_store_id": destination_store_id,
        "lines": [
            {
                "line_type": "EPC",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-TR-1",
                    "description": "Transfer EPC",
                    "var1_value": "Blue",
                    "var2_value": "L",
                    "epc": epc,
                    "location_code": "LOC-1",
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
    }


def _create_sale(client, token: str, store_id: str, *, create_txn: str, idempotency_key: str):
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json={
            "transaction_id": create_txn,
            "store_id": store_id,
            "lines": [
                sale_line(line_type="SKU", qty=1, unit_price=12.0, sku="SKU-CHECKOUT", epc=None, status="PENDING"),
            ],
        },
    )
    assert response.status_code == 201
    return response.json()["header"]["id"]


def test_smoke_auth_login_and_me(client, db_session):
    run_seed(db_session)
    tenant, store, _ = _seed_tenant_context(db_session, suffix="auth")
    user = _create_user(db_session, tenant=tenant, store=store, username="smoke-auth")

    token = _login(client, user.username)
    me = client.get("/aris3/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["tenant_id"] == str(tenant.id)


def test_smoke_stock_query_contract_and_totals_invariant(client, db_session):
    run_seed(db_session)
    tenant, store, _ = _seed_tenant_context(db_session, suffix="stock")
    user = _create_user(db_session, tenant=tenant, store=store, username="smoke-stock")

    db_session.add_all(
        [
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-1", epc="E" * 24, status="RFID", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-1", epc=None, status="PENDING", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-1", epc=None, status="PENDING", location_is_vendible=False),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-1", epc=None, status="IN_TRANSIT", location_is_vendible=False),
        ]
    )
    db_session.commit()

    token = _login(client, user.username)
    response = client.get("/aris3/stock", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"meta", "rows", "totals"}
    totals = payload["totals"]
    assert totals["total_units"] == totals["total_rfid"] + totals["total_pending"]


def test_smoke_transfer_action_lifecycle(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store = _seed_tenant_context(db_session, suffix="transfer")
    origin_user = _create_user(db_session, tenant=tenant, store=origin_store, username="smoke-transfer-origin")
    destination_user = _create_user(db_session, tenant=tenant, store=destination_store, username="smoke-transfer-dest")

    epc = "T" * 24
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku="SKU-TR-1",
            epc=epc,
            status="RFID",
            location_code="LOC-1",
            pool="P1",
            location_is_vendible=True,
        )
    )
    db_session.commit()

    origin_token = _login(client, origin_user.username)
    destination_token = _login(client, destination_user.username)

    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "smoke-transfer-create"},
        json=_transfer_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]
    line_id = create_response.json()["lines"][0]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "smoke-transfer-dispatch"},
        json={"transaction_id": "txn-smoke-transfer-dispatch", "action": "dispatch"},
    )
    assert dispatch.status_code == 200

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "smoke-transfer-receive"},
        json={
            "transaction_id": "txn-smoke-transfer-receive",
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


def test_smoke_pos_checkout_cash_precondition_and_reports_exports(client, db_session):
    run_seed(db_session)
    tenant, store, _ = _seed_tenant_context(db_session, suffix="checkout")
    user = _create_user(db_session, tenant=tenant, store=store, username="smoke-pos")
    token = _login(client, user.username)

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CHECKOUT",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale_id = _create_sale(
        client,
        token,
        str(store.id),
        create_txn="txn-smoke-sale-create-no-cash",
        idempotency_key="smoke-sale-create-no-cash",
    )
    checkout_fail = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "smoke-sale-checkout-no-cash"},
        json={
            "transaction_id": "txn-smoke-sale-checkout-no-cash",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 12.0}],
        },
    )
    assert checkout_fail.status_code == 422

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CHECKOUT",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    sale_id_ok = _create_sale(
        client,
        token,
        str(store.id),
        create_txn="txn-smoke-sale-create-ok",
        idempotency_key="smoke-sale-create-ok",
    )
    checkout_ok = client.post(
        f"/aris3/pos/sales/{sale_id_ok}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "smoke-sale-checkout-ok"},
        json={
            "transaction_id": "txn-smoke-sale-checkout-ok",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 12.0}],
        },
    )
    assert checkout_ok.status_code == 200

    today = date.today().isoformat()
    overview = client.get(
        "/aris3/reports/overview",
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert overview.status_code == 200

    exports_list = client.get("/aris3/exports", headers={"Authorization": f"Bearer {token}"})
    assert exports_list.status_code == 200


def test_smoke_idempotency_replay_critical_mutations(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store = _seed_tenant_context(db_session, suffix="idem")
    user = _create_user(db_session, tenant=tenant, store=origin_store, username="smoke-idem")
    token = _login(client, user.username)

    import_payload = {
        "transaction_id": "txn-smoke-import-sku",
        "tenant_id": str(tenant.id),
        "lines": [
            {
                "qty": 1,
                "sku": "SKU-IDEMP",
                "description": "Idem SKU",
                "var1_value": "V1",
                "var2_value": "V2",
                "epc": None,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "PENDING",
                "location_is_vendible": True,
                "image_asset_id": str(uuid.uuid4()),
                "image_url": "https://example.com/i.png",
                "image_thumb_url": "https://example.com/t.png",
                "image_source": "catalog",
                "image_updated_at": datetime.utcnow().isoformat(),
            }
        ],
    }
    h_import = {"Authorization": f"Bearer {token}", "Idempotency-Key": "smoke-idem-import"}
    import_first = client.post("/aris3/stock/import-sku", headers=h_import, json=import_payload)
    import_second = client.post("/aris3/stock/import-sku", headers=h_import, json=import_payload)
    assert import_first.status_code == 201
    assert import_second.status_code == 201
    assert import_second.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"

    epc = "I" * 24
    db_session.add(StockItem(id=uuid.uuid4(), tenant_id=tenant.id, sku="SKU-IDEM-EPC", epc=epc, status="RFID", location_code="LOC-1", pool="P1", location_is_vendible=True))
    db_session.commit()

    transfer_create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "smoke-idem-transfer-create"},
        json=_transfer_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert transfer_create.status_code == 201
    transfer_id = transfer_create.json()["header"]["id"]

    dispatch_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "smoke-idem-transfer-dispatch"}
    dispatch_payload = {"transaction_id": "txn-smoke-idem-dispatch", "action": "dispatch"}
    dispatch_first = client.post(f"/aris3/transfers/{transfer_id}/actions", headers=dispatch_headers, json=dispatch_payload)
    dispatch_second = client.post(f"/aris3/transfers/{transfer_id}/actions", headers=dispatch_headers, json=dispatch_payload)
    assert dispatch_first.status_code == 200
    assert dispatch_second.status_code == 200
    assert dispatch_second.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(origin_store.id), cashier_user_id=str(user.id))
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CHECKOUT",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    sale_id = _create_sale(
        client,
        token,
        str(origin_store.id),
        create_txn="txn-smoke-idem-sale-create",
        idempotency_key="smoke-idem-sale-create",
    )

    checkout_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "smoke-idem-checkout"}
    checkout_payload = {
        "transaction_id": "txn-smoke-idem-checkout",
        "action": "checkout",
        "payments": [{"method": "CASH", "amount": 12.0}],
    }
    checkout_first = client.post(f"/aris3/pos/sales/{sale_id}/actions", headers=checkout_headers, json=checkout_payload)
    checkout_second = client.post(f"/aris3/pos/sales/{sale_id}/actions", headers=checkout_headers, json=checkout_payload)
    assert checkout_first.status_code == 200
    assert checkout_second.status_code == 200
    assert checkout_second.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"
