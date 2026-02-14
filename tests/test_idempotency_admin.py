import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _create_tenant_store(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    db_session.add_all([tenant, store])
    db_session.commit()
    return tenant, store


def _create_user(db_session, *, tenant, store, role: str, username: str, password: str):
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


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_store_create_idempotency_and_conflict(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, suffix="IdemStore")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-idem-store", password="Pass1234!")

    token = _login(client, "admin-idem-store", "Pass1234!")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "store-idem-1"}
    payload = {"name": "A Store"}

    first = client.post("/aris3/admin/stores", headers=headers, json=payload)
    assert first.status_code == 201

    replay = client.post("/aris3/admin/stores", headers=headers, json=payload)
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"

    conflict = client.post("/aris3/admin/stores", headers=headers, json={"name": "Another Store"})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"


def test_store_create_accepts_legacy_x_idempotency_key(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, suffix="LegacyHeader")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-legacy", password="Pass1234!")

    token = _login(client, "admin-legacy", "Pass1234!")
    headers = {"Authorization": f"Bearer {token}", "X-Idempotency-Key": "legacy-store-idem-1"}

    response = client.post("/aris3/admin/stores", headers=headers, json={"name": "Legacy Header Store"})
    assert response.status_code == 201
