import uuid
from datetime import datetime

from sqlalchemy import text

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


def _seed_stock(db_session, tenant_id, *, epc: str):
    db_session.add(
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
    )
    db_session.commit()


def _transfer_payload(origin_store_id: str, destination_store_id: str, epc: str):
    return {
        "transaction_id": "txn-cancel-1",
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
            }
        ],
    }


def test_transfer_cancel_draft_success(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="cancel-draft")
    token = _login(client, user.username, "Pass1234!")

    payload = _transfer_payload(str(store.id), str(other_store.id), "E" * 24)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-1"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]

    cancel_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-2"},
        json={"transaction_id": "txn-cancel-2", "action": "cancel"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["header"]["status"] == "CANCELLED"


def test_transfer_cancel_dispatched_success(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="cancel-dispatched")
    token = _login(client, user.username, "Pass1234!")

    epc = "F" * 24
    _seed_stock(db_session, tenant.id, epc=epc)
    payload = _transfer_payload(str(store.id), str(other_store.id), epc)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-3"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]

    dispatch_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-4"},
        json={"transaction_id": "txn-cancel-3", "action": "dispatch"},
    )
    assert dispatch_response.status_code == 200

    cancel_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-5"},
        json={"transaction_id": "txn-cancel-4", "action": "cancel"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["header"]["status"] == "CANCELLED"


def test_transfer_cancel_invalid_state_denied(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="cancel-invalid")
    token = _login(client, user.username, "Pass1234!")

    epc = "G" * 24
    _seed_stock(db_session, tenant.id, epc=epc)
    payload = _transfer_payload(str(store.id), str(other_store.id), epc)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-6"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]

    dispatch_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-7"},
        json={"transaction_id": "txn-cancel-5", "action": "dispatch"},
    )
    assert dispatch_response.status_code == 200

    db_session.execute(
        text("UPDATE transfers SET received_at = :received WHERE id = :transfer_id"),
        {"received": datetime.utcnow(), "transfer_id": transfer_id},
    )
    db_session.commit()

    cancel_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-cancel-8"},
        json={"transaction_id": "txn-cancel-6", "action": "cancel"},
    )
    assert cancel_response.status_code == 422
    assert cancel_response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
