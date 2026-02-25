import uuid
from datetime import datetime, timedelta

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


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

    response = client.get("/aris3/stock", headers=headers)
    assert response.status_code == 200
    assert any(row["store_id"] is None for row in response.json()["rows"])

    filtered = client.get("/aris3/stock", params={"store_id": str(store_b.id)}, headers=headers)
    assert filtered.status_code == 200
    rows = filtered.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["sku"] == "SKU-B"
    assert rows[0]["store_id"] == str(store_b.id)


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
