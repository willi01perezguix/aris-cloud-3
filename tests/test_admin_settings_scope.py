import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_store(db_session, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Settings tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Settings store {suffix}")
    db_session.add_all([tenant, store])
    db_session.commit()
    return tenant, store


def _create_admin(db_session, *, tenant: Tenant, store: Store, username: str):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_return_policy_scope_rules_match_variant_fields(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, "A")
    tenant_b, _store_b = _create_tenant_store(db_session, "B")
    admin = _create_admin(db_session, tenant=tenant_a, store=store_a, username="settings-admin-a")

    tenant_admin_token = _login(client, admin.username, "Pass1234!")
    mismatch = client.get(
        f"/aris3/admin/settings/return-policy?tenant_id={tenant_b.id}",
        headers={"Authorization": f"Bearer {tenant_admin_token}"},
    )
    assert mismatch.status_code == 403
    assert mismatch.json()["code"] == "TENANT_SCOPE_MISMATCH"

    superadmin_token = _login(client, "superadmin", "change-me")
    missing_tenant = client.get(
        "/aris3/admin/settings/return-policy",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert missing_tenant.status_code == 400

    ok = client.get(
        f"/aris3/admin/settings/return-policy?tenant_id={tenant_a.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert ok.status_code == 200
