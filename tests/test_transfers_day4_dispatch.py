import uuid
from datetime import datetime

from app.aris3.core.error_catalog import ErrorCatalog
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


def _seed_stock(db_session, tenant_id, *, epc: str, qty: int):
    items = [
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku="SKU-1",
            description="Blue Jacket",
            var1_value="Blue",
            var2_value="L",
            epc=epc,
            location_code="LOC-1",
            pool="P1",
            status="RFID",
            location_is_vendible=True,
            image_asset_id=uuid.uuid4(),
            image_url="https://example.com/img.png",
            image_thumb_url="https://example.com/thumb.png",
            image_source="catalog",
            image_updated_at=datetime.utcnow(),
        )
    ]
    for _ in range(qty):
        items.append(
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                sku="SKU-2",
                description="Green Tee",
                var1_value="Green",
                var2_value="M",
                epc=None,
                location_code="LOC-1",
                pool="P1",
                status="PENDING",
                location_is_vendible=True,
                image_asset_id=uuid.uuid4(),
                image_url="https://example.com/img2.png",
                image_thumb_url="https://example.com/thumb2.png",
                image_source="catalog",
                image_updated_at=datetime.utcnow(),
            )
        )
    db_session.add_all(items)
    db_session.commit()


def _transfer_payload(origin_store_id: str, destination_store_id: str, epc: str, qty: int):
    return {
        "transaction_id": "txn-dispatch-1",
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
                    "epc": epc,
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
                "qty": qty,
                "snapshot": {
                    "sku": "SKU-2",
                    "description": "Green Tee",
                    "var1_value": "Green",
                    "var2_value": "M",
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


def test_transfer_dispatch_success(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="dispatch")
    token = _login(client, user.username, "Pass1234!")

    epc = "C" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    payload = _transfer_payload(str(store.id), str(other_store.id), epc, qty=2)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-dispatch-1"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]

    dispatch_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-dispatch-2"},
        json={"transaction_id": "txn-dispatch-2", "action": "dispatch"},
    )
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["header"]["status"] == "DISPATCHED"

    in_transit = (
        db_session.query(StockItem)
        .filter(
            StockItem.tenant_id == tenant.id,
            StockItem.pool == "IN_TRANSIT",
            StockItem.location_code == "IN_TRANSIT",
            StockItem.location_is_vendible.is_(False),
        )
        .count()
    )
    assert in_transit == 3

    total_rfid = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "RFID")
        .count()
    )
    total_pending = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "PENDING")
        .count()
    )
    assert total_rfid + total_pending == 3


def test_transfer_dispatch_insufficient_stock(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="dispatch-short")
    token = _login(client, user.username, "Pass1234!")

    epc = "D" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=1)

    payload = _transfer_payload(str(store.id), str(other_store.id), epc, qty=3)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-dispatch-3"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]

    dispatch_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-dispatch-4"},
        json={"transaction_id": "txn-dispatch-4", "action": "dispatch"},
    )
    assert dispatch_response.status_code == 422
    assert dispatch_response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
