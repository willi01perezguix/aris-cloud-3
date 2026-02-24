import uuid
from datetime import datetime

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_user(db_session, *, suffix: str, role: str = "ADMIN"):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    other_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix} B")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"user-{suffix}",
        email=f"user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role=role,
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store, other_store, user])
    db_session.commit()
    return tenant, store, other_store, user


def _transfer_payload(origin_store_id: str, destination_store_id: str):
    return {
        "transaction_id": "txn-create-1",
        "origin_store_id": origin_store_id,
        "destination_store_id": destination_store_id,
        "lines": [
            {
                "line_type": "EPC",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-1",
                    "description": "Blue Jacket",
                    "var1_value": "Blue",
                    "var2_value": "L",
                    "cost_price": 25.0,
                    "suggested_price": 35.0,
                    "sale_price": 32.5,
                    "epc": "A" * 24,
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "status": "RFID",
                    "location_is_vendible": True,
                    "image_asset_id": str(uuid.uuid4()),
                    "image_url": "https://example.com/img.png",
                    "image_thumb_url": "https://example.com/thumb.png",
                    "image_source": "catalog",
                    "image_updated_at": datetime.utcnow().isoformat(),
                },
            },
            {
                "line_type": "SKU",
                "qty": 2,
                "snapshot": {
                    "sku": "SKU-2",
                    "description": "Green Tee",
                    "var1_value": "Green",
                    "var2_value": "M",
                    "cost_price": 10.0,
                    "suggested_price": 15.0,
                    "sale_price": 12.5,
                    "epc": None,
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "status": "PENDING",
                    "location_is_vendible": True,
                    "image_asset_id": str(uuid.uuid4()),
                    "image_url": "https://example.com/img2.png",
                    "image_thumb_url": "https://example.com/thumb2.png",
                    "image_source": "catalog",
                    "image_updated_at": datetime.utcnow().isoformat(),
                },
            },
        ],
    }


def test_transfer_create_list_detail(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="create")
    token = _login(client, user.username, "Pass1234!")

    payload = _transfer_payload(str(store.id), str(other_store.id))
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-create-1"},
        json=payload,
    )
    assert response.status_code == 201
    transfer_id = response.json()["header"]["id"]

    list_response = client.get(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert any(row["header"]["id"] == transfer_id for row in list_response.json()["rows"])

    detail_response = client.get(
        f"/aris3/transfers/{transfer_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["header"]["status"] == "DRAFT"
    for line in detail_response.json()["lines"]:
        assert "cost_price" in line["snapshot"]
        assert "suggested_price" in line["snapshot"]
        assert "sale_price" in line["snapshot"]


def test_transfer_list_tenant_scoped(client, db_session):
    run_seed(db_session)
    tenant_a, store_a, other_store_a, user_a = _create_tenant_user(db_session, suffix="list-a")
    tenant_b, store_b, other_store_b, user_b = _create_tenant_user(db_session, suffix="list-b")

    token_a = _login(client, user_a.username, "Pass1234!")
    payload = _transfer_payload(str(store_a.id), str(other_store_a.id))
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "transfer-create-2"},
        json=payload,
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["header"]["id"]

    token_b = _login(client, user_b.username, "Pass1234!")
    list_response = client.get(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert list_response.status_code == 200
    assert all(row["header"]["id"] != created_id for row in list_response.json()["rows"])


def test_transfer_create_bodega_to_store_same_tenant(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant bodega")
    bodega_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="BODEGA")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Operativa")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=bodega_store.id,
        username="user-bodega",
        email="user-bodega@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, bodega_store, store, user])
    db_session.commit()
    token = _login(client, user.username, "Pass1234!")

    payload = _transfer_payload(str(bodega_store.id), str(store.id))
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-create-bodega-1"},
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["header"]["origin_store_id"] == str(bodega_store.id)
    assert response.json()["header"]["destination_store_id"] == str(store.id)

