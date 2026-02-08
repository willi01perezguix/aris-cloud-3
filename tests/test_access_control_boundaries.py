import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import PermissionCatalog, Store, Tenant, User
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
        store_id=store.id if store else None,
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


def _login(client, username: str, password: str):
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_cannot_cross_tenant_with_user_overrides(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="BoundaryA")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="BoundaryB")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin-b", password="Pass1234!")
    user_b = _create_user(db_session, tenant=tenant_b, store=store_b, role="USER", username="user-b", password="Pass1234!")

    token = _login(client, "admin-b", "Pass1234!")
    response = client.get(
        f"/aris3/admin/access-control/user-overrides/{user_b.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"


def test_admin_ceiling_blocks_elevation_on_tenant_policy(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="BoundaryCeiling")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-c", password="Pass1234!")
    db_session.add(PermissionCatalog(code="SECRET_BOUNDARY", description="Hidden"))
    db_session.commit()

    token = _login(client, "admin-c", "Pass1234!")
    response = client.put(
        "/aris3/admin/access-control/tenant-role-policies/USER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "boundary-1"},
        json={"allow": ["SECRET_BOUNDARY"], "deny": [], "transaction_id": "txn-b-1"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
