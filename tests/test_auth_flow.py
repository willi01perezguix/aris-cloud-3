import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Tenant, User


def test_login_change_password_flow(client, db_session):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant A")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        username="jane",
        email="jane@example.com",
        hashed_password=get_password_hash("old-pass"),
        role="admin",
        must_change_password=True,
        is_active=True,
    )
    db_session.add(tenant)
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": "jane", "password": "old-pass"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json()["must_change_password"] is True

    me_response = client.get("/aris3/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "jane"

    change_response = client.post(
        "/aris3/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "old-pass", "new_password": "new-pass"},
    )
    assert change_response.status_code == 200
    assert change_response.json()["must_change_password"] is False

    login_again = client.post(
        "/aris3/auth/login",
        json={"username_or_email": "jane@example.com", "password": "new-pass"},
    )
    assert login_again.status_code == 200
    assert login_again.json()["must_change_password"] is False
