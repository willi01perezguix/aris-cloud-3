import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User


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


def test_login_success(client, db_session):
    _create_user(db_session)

    response = client.post(
        "/aris3/auth/login",
        json={"email": "jane@example.com", "password": "OldPass123"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["must_change_password"] is True


def test_login_invalid_password(client, db_session):
    _create_user(db_session)

    response = client.post(
        "/aris3/auth/login",
        json={"email": "jane@example.com", "password": "wrong-pass"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "http_error"


def test_login_blocked_inactive(client, db_session):
    _create_user(db_session, is_active=False)

    response = client.post(
        "/aris3/auth/login",
        json={"email": "jane@example.com", "password": "OldPass123"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "http_error"


def test_login_blocked_suspended(client, db_session):
    _create_user(db_session, status="suspended")

    response = client.post(
        "/aris3/auth/login",
        json={"email": "jane@example.com", "password": "OldPass123"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "http_error"


def test_must_change_password_flow(client, db_session):
    _create_user(db_session, must_change_password=True)

    response = client.post(
        "/aris3/auth/login",
        json={"email": "jane@example.com", "password": "OldPass123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json()["must_change_password"] is True

    change_response = client.post(
        "/aris3/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
    )
    assert change_response.status_code == 200
    new_token = change_response.json()["access_token"]
    assert change_response.json()["must_change_password"] is False

    me_response = client.get("/aris3/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_response.status_code == 200
    assert me_response.json()["must_change_password"] is False


def test_me_unauthorized(client):
    response = client.get("/aris3/me")
    assert response.status_code == 401
    assert response.json()["code"] == "http_error"
    assert response.json()["trace_id"]


def test_me_authorized(client, db_session):
    tenant, user = _create_user(db_session)

    response = client.post(
        "/aris3/auth/login",
        json={"email": "jane@example.com", "password": "OldPass123"},
    )
    token = response.json()["access_token"]

    me_response = client.get("/aris3/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["tenant_id"] == str(tenant.id)
    assert payload["store_id"] == str(user.store_id)
    assert payload["role"] == "admin"
    assert payload["status"] == "active"
    assert payload["is_active"] is True
