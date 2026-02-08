import uuid

from app.aris3.core.config import settings
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _create_tenant_store(db_session, *, name_suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {name_suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {name_suffix}")
    db_session.add(tenant)
    db_session.add(store)
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
    return user


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_effective_permissions_target_scope(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="TargetA")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="TargetB")
    admin = _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin", password="Pass1234!")
    user_a = _create_user(db_session, tenant=tenant_a, store=store_a, role="USER", username="user-a", password="Pass1234!")
    user_b = _create_user(db_session, tenant=tenant_b, store=store_b, role="USER", username="user-b", password="Pass1234!")

    admin_token = _login(client, "admin", "Pass1234!")
    admin_response = client.get(
        f"/aris3/access-control/effective-permissions/users/{user_a.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["user_id"] == str(user_a.id)

    cross_response = client.get(
        f"/aris3/access-control/effective-permissions/users/{user_b.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cross_response.status_code == 403
    assert cross_response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

    super_token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)
    super_response = client.get(
        f"/aris3/access-control/effective-permissions/users/{user_b.id}",
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert super_response.status_code == 200

    user_token = _login(client, "user-a", "Pass1234!")
    self_response = client.get(
        f"/aris3/access-control/effective-permissions/users/{user_a.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert self_response.status_code == 200

    denied_response = client.get(
        f"/aris3/access-control/effective-permissions/users/{admin.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert denied_response.status_code == 403
    assert denied_response.json()["code"] == "PERMISSION_DENIED"
