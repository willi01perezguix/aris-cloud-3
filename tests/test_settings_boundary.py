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


def test_settings_tenant_boundaries_and_roles(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="SettingsA")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="SettingsB")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin-a", password="Pass1234!")
    _create_user(db_session, tenant=tenant_b, store=store_b, role="ADMIN", username="admin-b", password="Pass1234!")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="USER", username="user-a", password="Pass1234!")

    admin_a_token = _login(client, "admin-a", "Pass1234!")
    patch_response = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {admin_a_token}", "Idempotency-Key": "settings-a-1"},
        json={"var1_label": "Color"},
    )
    assert patch_response.status_code == 200

    admin_b_token = _login(client, "admin-b", "Pass1234!")
    get_response = client.get(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {admin_b_token}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["var1_label"] is None

    user_token = _login(client, "user-a", "Pass1234!")
    forbidden_get = client.get(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden_get.status_code == 403
    assert forbidden_get.json()["code"] == "PERMISSION_DENIED"

    forbidden_patch = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {user_token}", "Idempotency-Key": "settings-a-2"},
        json={"var1_label": "Size"},
    )
    assert forbidden_patch.status_code == 403
    assert forbidden_patch.json()["code"] == "PERMISSION_DENIED"

    super_token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)
    super_get = client.get(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert super_get.status_code == 200
