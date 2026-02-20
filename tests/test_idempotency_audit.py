import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import AuditEvent, Store, Tenant, User


def _create_user(db_session, **kwargs):
    tenant = kwargs.pop("tenant", Tenant(id=uuid.uuid4(), name="Tenant A"))
    store = kwargs.pop("store", Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store A"))
    user = User(
        id=kwargs.pop("id", uuid.uuid4()),
        tenant_id=tenant.id,
        store_id=kwargs.pop("store_id", store.id),
        username=kwargs.pop("username", "jane"),
        email=kwargs.pop("email", "jane@example.com"),
        hashed_password=kwargs.pop("hashed_password", get_password_hash("OldPass123")),
        role=kwargs.pop("role", "admin"),
        status=kwargs.pop("status", "active"),
        must_change_password=kwargs.pop("must_change_password", True),
        is_active=kwargs.pop("is_active", True),
    )
    db_session.add(tenant)
    db_session.add(store)
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _login(client, email: str, password: str):
    response = client.post(
        "/aris3/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_idempotency_replay_change_password(client, db_session):
    _create_user(db_session)
    token = _login(client, "jane@example.com", "OldPass123")

    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "change-1"}
    payload = {"current_password": "OldPass123", "new_password": "NewPass45678"}

    first = client.post("/aris3/auth/change-password", headers=headers, json=payload)
    assert first.status_code == 200

    replay = client.post("/aris3/auth/change-password", headers=headers, json=payload)
    assert replay.status_code == first.status_code
    assert replay.json() == first.json()
    assert replay.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"


def test_idempotency_conflict_change_password(client, db_session):
    _create_user(db_session, email="jane2@example.com", username="jane2")
    token = _login(client, "jane2@example.com", "OldPass123")

    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "change-2"}
    payload = {"current_password": "OldPass123", "new_password": "NewPass45678"}
    client.post("/aris3/auth/change-password", headers=headers, json=payload)

    conflict = client.post(
        "/aris3/auth/change-password",
        headers=headers,
        json={"current_password": "OldPass123", "new_password": "AnotherPass7890"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"


def test_change_password_without_idempotency_key(client, db_session):
    _create_user(db_session, email="jane3@example.com", username="jane3")
    token = _login(client, "jane3@example.com", "OldPass123")

    response = client.post(
        "/aris3/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "OldPass123", "new_password": "NewPass45678"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["trace_id"]


def test_audit_event_created_on_change_password(client, db_session):
    _create_user(db_session, email="jane4@example.com", username="jane4")
    token = _login(client, "jane4@example.com", "OldPass123")

    response = client.post(
        "/aris3/auth/change-password",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "change-4"},
        json={"current_password": "OldPass123", "new_password": "NewPass45678"},
    )
    assert response.status_code == 200

    event = db_session.query(AuditEvent).filter(AuditEvent.action == "auth.change_password").first()
    assert event is not None
    assert event.result == "success"
