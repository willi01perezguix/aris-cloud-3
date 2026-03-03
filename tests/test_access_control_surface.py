import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _seed_tenant_store_users(db_session):
    run_seed(db_session)

    tenant = Tenant(id=uuid.uuid4(), name="Tenant AC")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store AC")
    db_session.add_all([tenant, store])
    db_session.flush()

    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username="admin-ac",
        email="admin-ac@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username="user-ac",
        email="user-ac@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="USER",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([admin, user])
    db_session.commit()
    return admin, user


def _login(client, username: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": "Pass1234!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_public_self_access_control_endpoints_work_for_authenticated_user(client, db_session):
    _seed_tenant_store_users(db_session)
    token = _login(client, "user-ac")

    effective = client.get(
        "/aris3/access-control/effective-permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert effective.status_code == 200
    assert effective.json()["role"] == "USER"

    catalog = client.get(
        "/aris3/access-control/permission-catalog",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert catalog.status_code == 200
    assert len(catalog.json()["permissions"]) > 0


def test_admin_access_control_endpoints_remain_available_under_admin_prefix(client, db_session):
    admin, user = _seed_tenant_store_users(db_session)
    admin_token = _login(client, "admin-ac")

    permission_catalog = client.get(
        "/aris3/admin/access-control/permission-catalog",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert permission_catalog.status_code == 200

    effective = client.get(
        f"/aris3/admin/access-control/effective-permissions?user_id={user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert effective.status_code == 200


def test_legacy_public_endpoint_stays_callable_but_is_hidden_from_openapi(client, db_session):
    admin, _ = _seed_tenant_store_users(db_session)
    token = _login(client, "admin-ac")

    legacy_response = client.get(
        f"/aris3/access-control/effective-permissions/users/{admin.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert legacy_response.status_code == 200

    assert "/aris3/access-control/effective-permissions/users/{user_id}" not in client.app.openapi()["paths"]
