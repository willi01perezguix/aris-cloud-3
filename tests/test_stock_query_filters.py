import uuid
from datetime import datetime, timedelta

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed
from app.aris3.routers import stock as stock_router


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_user(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"admin-{suffix}",
        email=f"admin-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, user




def _create_tenant_user_with_store(db_session, *, suffix: str, tenant_id, store_id):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        username=f"admin-{suffix}",
        email=f"admin-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_store_user_with_role(db_session, *, suffix: str, tenant_id, store_id, role: str):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        username=f"user-{suffix}",
        email=f"user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role=role,
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _seed_items(db_session, tenant_id, store_id_a, store_id_b):
    now = datetime.utcnow()
    items = [
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku="SKU-RED",
            description="Red Jacket",
            var1_value="Red",
            var2_value="M",
            epc="EPC-RED",
            location_code="LOC-A",
            pool="P1",
            store_id=store_id_a,
            status="RFID",
            location_is_vendible=True,
            created_at=now - timedelta(days=2),
        ),
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku="SKU-BLUE",
            description="Blue Jacket",
            var1_value="Blue",
            var2_value="L",
            epc="EPC-BLUE",
            location_code="LOC-B",
            pool="P2",
            store_id=store_id_b,
            status="PENDING",
            location_is_vendible=True,
            created_at=now - timedelta(days=1),
        ),
    ]
    db_session.add_all(items)
    db_session.commit()
    return items


def test_stock_query_filters(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="filters")
    items = _seed_items(db_session, tenant.id, user.store_id, user.store_id)

    token = _login(client, user.username, "Pass1234!")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/aris3/stock", params={"sku": "SKU-RED"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["sku"] == "SKU-RED"

    response = client.get("/aris3/stock", params={"epc": "EPC-BLUE"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["epc"] == "EPC-BLUE"

    response = client.get("/aris3/stock", params={"location_code": "LOC-A"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["location_code"] == "LOC-A"

    response = client.get("/aris3/stock", params={"pool": "P2"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["pool"] == "P2"

    response = client.get("/aris3/stock", params={"q": "Blue"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["sku"] == "SKU-BLUE"

    response = client.get("/aris3/stock", params={"description": "Red"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["sku"] == "SKU-RED"

    response = client.get("/aris3/stock", params={"var1_value": "Blue"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["var1_value"] == "Blue"

    response = client.get("/aris3/stock", params={"var2_value": "M"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["var2_value"] == "M"

    from_date = (items[0].created_at + timedelta(hours=1)).isoformat()
    response = client.get("/aris3/stock", params={"from": from_date}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["sku"] == "SKU-BLUE"

    to_date = (items[0].created_at + timedelta(hours=1)).isoformat()
    response = client.get("/aris3/stock", params={"to": to_date}, headers=headers)
    assert response.status_code == 200
    assert response.json()["rows"][0]["sku"] == "SKU-RED"


def test_stock_query_store_id_filter_and_null(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant store-filter")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store B")
    db_session.add_all([tenant, store_a, store_b])
    db_session.commit()
    user = _create_tenant_user_with_store(db_session, suffix="store-filter", tenant_id=tenant.id, store_id=store_a.id)

    db_session.add_all([
        StockItem(id=uuid.uuid4(), tenant_id=tenant.id, store_id=store_a.id, sku="SKU-A", status="RFID", location_code="LOC-1", pool="SALE", location_is_vendible=True),
        StockItem(id=uuid.uuid4(), tenant_id=tenant.id, store_id=store_b.id, sku="SKU-B", status="RFID", location_code="LOC-2", pool="SALE", location_is_vendible=True),
        StockItem(id=uuid.uuid4(), tenant_id=tenant.id, store_id=None, sku="SKU-WH", status="PENDING", location_code="WH-MAIN", pool="BODEGA", location_is_vendible=False),
    ])
    db_session.commit()

    token = _login(client, user.username, "Pass1234!")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/aris3/stock", params={"scope": "tenant"}, headers=headers)
    assert response.status_code == 200
    assert any(row["store_id"] is None for row in response.json()["rows"])

    filtered = client.get("/aris3/stock", params={"scope": "tenant", "store_id": str(store_b.id)}, headers=headers)
    assert filtered.status_code == 200
    rows = filtered.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["sku"] == "SKU-B"
    assert rows[0]["store_id"] == str(store_b.id)


def test_stock_query_default_scope_is_self(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant self-scope")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store B")
    db_session.add_all([tenant, store_a, store_b])
    db_session.commit()
    user = _create_tenant_user_with_store(db_session, suffix="self-scope", tenant_id=tenant.id, store_id=store_a.id)
    _seed_items(db_session, tenant.id, store_a.id, store_b.id)

    token = _login(client, user.username, "Pass1234!")
    response = client.get("/aris3/stock", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert rows
    assert {row["store_id"] for row in rows} == {str(store_a.id)}
    assert response.json()["meta"]["scope"] == "self"


def test_stock_query_scope_tenant_includes_store_context_and_totals(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant tenant-scope")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store B")
    db_session.add_all([tenant, store_a, store_b])
    db_session.commit()
    user = _create_tenant_user_with_store(db_session, suffix="tenant-scope", tenant_id=tenant.id, store_id=store_a.id)
    _seed_items(db_session, tenant.id, store_a.id, store_b.id)

    token = _login(client, user.username, "Pass1234!")
    response = client.get("/aris3/stock", params={"scope": "tenant", "view": "all"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["scope"] == "tenant"
    assert {row["store_id"] for row in payload["rows"]} == {str(store_a.id), str(store_b.id)}
    assert all("store_name" in row for row in payload["rows"])
    assert all("is_current_store" in row for row in payload["rows"])
    assert payload["totals"]["totals_by_store"]
    assert {entry["store_id"] for entry in payload["totals"]["totals_by_store"]} == {str(store_a.id), str(store_b.id)}


def test_stock_query_scope_tenant_requires_broad_store_access(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant tenant-scope-restricted")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store B")
    db_session.add_all([tenant, store_a, store_b])
    db_session.commit()
    user = _create_store_user_with_role(
        db_session,
        suffix="tenant-scope-restricted",
        tenant_id=tenant.id,
        store_id=store_a.id,
        role="CASHIER",
    )
    _seed_items(db_session, tenant.id, store_a.id, store_b.id)

    token = _login(client, user.username, "Pass1234!")
    response = client.get("/aris3/stock", params={"scope": "tenant"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_stock_query_store_id_respects_tenant_scope(client, db_session):
    run_seed(db_session)
    tenant_a = Tenant(id=uuid.uuid4(), name="Tenant A")
    tenant_b = Tenant(id=uuid.uuid4(), name="Tenant B")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Store A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant_b.id, name="Store B")
    db_session.add_all([tenant_a, tenant_b, store_a, store_b])
    db_session.commit()
    user_a = _create_tenant_user_with_store(db_session, suffix="tenant-a", tenant_id=tenant_a.id, store_id=store_a.id)

    token = _login(client, user_a.username, "Pass1234!")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/aris3/stock", params={"store_id": str(store_b.id)}, headers=headers)
    assert response.status_code == 403


def test_stock_query_store_scope_no_cross_store_leakage_across_views(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant strict-store-scope")
    requested_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Requested Store")
    other_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Other Store")
    db_session.add_all([tenant, requested_store, other_store])
    db_session.commit()
    user = _create_tenant_user_with_store(
        db_session,
        suffix="strict-store-scope",
        tenant_id=tenant.id,
        store_id=requested_store.id,
    )

    db_session.add_all(
        [
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=requested_store.id,
                sku="SKU-REQ-PENDING",
                epc=None,
                status="PENDING",
                location_code="LOC-REQ",
                pool="SALE",
                location_is_vendible=True,
            ),
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=requested_store.id,
                sku="SKU-REQ-SOLD",
                epc="EPC-REQ-SOLD",
                status="SOLD",
                location_code="LOC-REQ",
                pool="SALE",
                location_is_vendible=True,
            ),
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=other_store.id,
                sku="SKU-OTHER-A",
                epc=None,
                status="RFID",
                location_code="LOC-OTHER",
                pool="SALE",
                location_is_vendible=True,
            ),
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=other_store.id,
                sku="SKU-OTHER-SOLD",
                epc="EPC-OTHER-SOLD",
                status="SOLD",
                location_code="LOC-OTHER",
                pool="SALE",
                location_is_vendible=True,
            ),
        ]
    )
    db_session.commit()

    token = _login(client, user.username, "Pass1234!")
    headers = {"Authorization": f"Bearer {token}"}
    scoped_params = {"store_id": str(requested_store.id)}

    default_response = client.get("/aris3/stock", params=scoped_params, headers=headers)
    assert default_response.status_code == 200
    default_rows = default_response.json()["rows"]
    assert all(row["store_id"] == str(requested_store.id) for row in default_rows)
    assert all(row["status"] != "SOLD" for row in default_rows)
    assert any(row["sku"] == "SKU-REQ-PENDING" for row in default_rows)
    assert {"available_for_sale", "available_for_transfer", "sale_mode", "transfer_mode", "available_qty"} <= set(
        default_rows[0].keys()
    )

    operational_false = client.get(
        "/aris3/stock",
        params={**scoped_params, "view": "operational", "include_sold": "false"},
        headers=headers,
    )
    assert operational_false.status_code == 200
    operational_false_rows = operational_false.json()["rows"]
    assert all(row["store_id"] == str(requested_store.id) for row in operational_false_rows)
    assert all(row["status"] != "SOLD" for row in operational_false_rows)
    pending_row = next(row for row in operational_false_rows if row["sku"] == "SKU-REQ-PENDING")
    assert pending_row["available_for_transfer"] is True
    assert pending_row["transfer_mode"] == "SKU"

    operational_true = client.get(
        "/aris3/stock",
        params={**scoped_params, "view": "operational", "include_sold": "true"},
        headers=headers,
    )
    assert operational_true.status_code == 200
    operational_true_rows = operational_true.json()["rows"]
    assert all(row["store_id"] == str(requested_store.id) for row in operational_true_rows)
    assert any(row["status"] == "SOLD" for row in operational_true_rows)
    assert all(row["sku"] in {"SKU-REQ-PENDING", "SKU-REQ-SOLD"} for row in operational_true_rows)


def test_stock_query_store_scope_strict_rows_and_totals_with_operational_view(client, db_session, monkeypatch):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant strict-live-hotfix")
    requested_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Requested Store")
    leaking_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Leaking Store")
    db_session.add_all([tenant, requested_store, leaking_store])
    db_session.commit()
    user = _create_tenant_user_with_store(
        db_session,
        suffix="strict-live-hotfix",
        tenant_id=tenant.id,
        store_id=requested_store.id,
    )

    db_session.add_all(
        [
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=requested_store.id,
                sku="SKU-TARGET-001",
                epc=None,
                status="PENDING",
                location_code="LOC-TARGET",
                pool="SALE",
                location_is_vendible=True,
            ),
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=leaking_store.id,
                sku="SKU-SMOKE-A",
                epc=None,
                status="PENDING",
                location_code="LOC-LEAK",
                pool="SALE",
                location_is_vendible=True,
            ),
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=leaking_store.id,
                sku="SKU-VERIFY-003",
                epc=None,
                status="PENDING",
                location_code="LOC-LEAK",
                pool="SALE",
                location_is_vendible=True,
            ),
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=leaking_store.id,
                sku="SKU-TEST-001",
                epc=None,
                status="PENDING",
                location_code="LOC-LEAK",
                pool="SALE",
                location_is_vendible=True,
            ),
        ]
    )
    db_session.commit()

    forensic_messages: list[str] = []

    def _capture_log(message, *args, **kwargs):
        forensic_messages.append(message % args)

    monkeypatch.setattr(stock_router.logger, "info", _capture_log)

    token = _login(client, user.username, "Pass1234!")
    response = client.get(
        "/aris3/stock",
        params={
            "store_id": str(requested_store.id),
            "view": "operational",
            "include_sold": "false",
            "page": 1,
            "page_size": 50,
            "sort_by": "created_at",
            "sort_dir": "desc",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    rows = body["rows"]
    assert rows
    assert {row["store_id"] for row in rows} == {str(requested_store.id)}
    assert {row["sku"] for row in rows} == {"SKU-TARGET-001"}
    assert body["totals"]["total_rows"] == 1
    assert body["totals"]["total_pending"] == 1
    assert body["totals"]["total_units"] == 1
    assert "available_for_transfer" in rows[0]
    assert rows[0]["transfer_mode"] == "SKU"

    forensic_logs = [message for message in forensic_messages if "stock_query_forensics" in message]
    assert forensic_logs, "Expected stock_query_forensics log entry"
    forensic_log = forensic_logs[-1]
    assert "requested_store_id=" in forensic_log
    assert "resolved_store_id=" in forensic_log
    assert "token_store_id=" in forensic_log
    assert "base_sql=" in forensic_log
    assert "paged_sql=" in forensic_log
    assert str(requested_store.id) in forensic_log
    assert "SKU-SMOKE-A" not in {row["sku"] for row in rows}
