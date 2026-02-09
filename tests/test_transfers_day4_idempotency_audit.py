import uuid
from datetime import datetime

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import AuditEvent, Store, Tenant, User
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
        "transaction_id": "txn-idem-1",
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


def test_transfer_idempotency_replay_and_conflict(client, db_session):
    run_seed(db_session)
    _tenant, store, other_store, user = _create_tenant_user(db_session, suffix="idem")
    token = _login(client, user.username, "Pass1234!")

    payload = _transfer_payload(str(store.id), str(other_store.id))
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-idem-1"}

    first = client.post("/aris3/transfers", headers=headers, json=payload)
    assert first.status_code == 201

    replay = client.post("/aris3/transfers", headers=headers, json=payload)
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.headers.get("X-Idempotency-Result") == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict = client.post(
        "/aris3/transfers",
        headers=headers,
        json={
            **payload,
            "transaction_id": "txn-idem-2",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code


def test_transfer_audit_event_created(client, db_session):
    run_seed(db_session)
    _tenant, store, other_store, user = _create_tenant_user(db_session, suffix="audit")
    token = _login(client, user.username, "Pass1234!")

    payload = _transfer_payload(str(store.id), str(other_store.id))
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-audit-1"},
        json=payload,
    )
    assert response.status_code == 201

    event = db_session.query(AuditEvent).filter(AuditEvent.action == "transfer.create").first()
    assert event is not None
    assert event.result == "success"
