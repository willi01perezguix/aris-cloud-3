import uuid
from datetime import datetime

from app.aris3.core.error_catalog import ErrorCatalog
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
        "transaction_id": "txn-security-1",
        "origin_store_id": origin_store_id,
        "destination_store_id": destination_store_id,
        "lines": [
            {
                "line_type": "SKU",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-1",
                    "description": "Blue Jacket",
                    "var1_value": "Blue",
                    "var2_value": "L",
                    "epc": None,
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "status": "PENDING",
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


def test_transfer_cross_tenant_denied(client, db_session):
    run_seed(db_session)
    tenant_a, store_a, other_store_a, user_a = _create_tenant_user(db_session, suffix="sec-a")
    tenant_b, store_b, other_store_b, user_b = _create_tenant_user(db_session, suffix="sec-b")

    token_a = _login(client, user_a.username, "Pass1234!")
    payload = _transfer_payload(str(store_b.id), str(other_store_b.id))
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "transfer-sec-1"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_transfer_origin_destination_same_denied(client, db_session):
    run_seed(db_session)
    _tenant, store, _other_store, user = _create_tenant_user(db_session, suffix="sec-c")
    token = _login(client, user.username, "Pass1234!")

    payload = _transfer_payload(str(store.id), str(store.id))
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-sec-2"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_transfer_rbac_denied(client, db_session):
    run_seed(db_session)
    _tenant, store, other_store, user = _create_tenant_user(db_session, suffix="sec-d", role="USER")
    token = _login(client, user.username, "Pass1234!")

    payload = _transfer_payload(str(store.id), str(other_store.id))
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-sec-3"},
        json=payload,
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code


def test_transfer_rejects_mixed_tenant_origin_destination(client, db_session):
    run_seed(db_session)
    tenant_a, store_a, _other_store_a, user_a = _create_tenant_user(db_session, suffix="sec-mix-a")
    _tenant_b, store_b, _other_store_b, _user_b = _create_tenant_user(db_session, suffix="sec-mix-b")

    token_a = _login(client, user_a.username, "Pass1234!")
    payload = _transfer_payload(str(store_a.id), str(store_b.id))
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "transfer-sec-4"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

