import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import AuditEvent, PermissionCatalog, Store, Tenant, User
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


def _login(client, username: str, password: str):
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_can_manage_role_policy_and_is_audited(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="AdminPolicy")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin", password="Pass1234!")

    token = _login(client, "admin", "Pass1234!")
    payload = {"allow": ["AUDIT_VIEW"], "deny": ["STORE_VIEW"]}
    response = client.put(
        f"/aris3/access-control/tenants/{tenant.id}/role-policies/MANAGER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "role-1"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["allow"] == ["AUDIT_VIEW"]
    assert body["deny"] == ["STORE_VIEW"]

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.action == "access_control.role_policy.update")
        .first()
    )
    assert event is not None
    assert event.result == "success"


def test_admin_cannot_escalate_past_ceiling(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Ceiling")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin2", password="Pass1234!")
    db_session.add(PermissionCatalog(code="SECRET_VIEW", description="Hidden"))
    db_session.commit()

    token = _login(client, "admin2", "Pass1234!")
    response = client.put(
        f"/aris3/access-control/tenants/{tenant.id}/role-policies/USER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "role-2"},
        json={"allow": ["SECRET_VIEW"], "deny": []},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_admin_cannot_bypass_ceiling_with_user_overrides(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="OverrideCeiling")
    _create_user(
        db_session,
        tenant=tenant,
        store=store,
        role="ADMIN",
        username="admin-ceiling",
        password="Pass1234!",
    )
    user = _create_user(
        db_session,
        tenant=tenant,
        store=store,
        role="USER",
        username="user-ceiling",
        password="Pass1234!",
    )
    db_session.add(PermissionCatalog(code="SECRET_OVERRIDE", description="Hidden"))
    db_session.commit()

    token = _login(client, "admin-ceiling", "Pass1234!")
    response = client.put(
        f"/aris3/access-control/tenants/{tenant.id}/users/{user.id}/permission-overrides",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "override-ceiling-1"},
        json={"allow": ["SECRET_OVERRIDE"], "deny": []},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_cross_tenant_role_policy_write_denied(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="A")
    tenant_b, _store_b = _create_tenant_store(db_session, name_suffix="B")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin3", password="Pass1234!")

    token = _login(client, "admin3", "Pass1234!")
    response = client.put(
        f"/aris3/access-control/tenants/{tenant_b.id}/role-policies/USER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "role-3"},
        json={"allow": ["STORE_VIEW"], "deny": []},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"


def test_user_override_updates_effective_permissions_and_requires_idempotency(
    client, db_session
):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Override")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin4", password="Pass1234!")
    user = _create_user(db_session, tenant=tenant, store=store, role="USER", username="user4", password="Pass1234!")

    token = _login(client, "admin4", "Pass1234!")
    policy_payload = {"allow": ["USER_MANAGE"], "deny": ["STORE_VIEW"]}
    policy_response = client.put(
        f"/aris3/access-control/tenants/{tenant.id}/role-policies/USER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "role-4"},
        json=policy_payload,
    )
    assert policy_response.status_code == 200

    override_response = client.put(
        f"/aris3/access-control/tenants/{tenant.id}/users/{user.id}/permission-overrides",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "override-1"},
        json={"allow": ["AUDIT_VIEW"], "deny": ["USER_MANAGE"]},
    )
    assert override_response.status_code == 200

    missing_idempotency = client.put(
        f"/aris3/access-control/tenants/{tenant.id}/users/{user.id}/permission-overrides",
        headers={"Authorization": f"Bearer {token}"},
        json={"allow": ["AUDIT_VIEW"], "deny": ["USER_MANAGE"]},
    )
    assert missing_idempotency.status_code == 400
    assert missing_idempotency.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    user_token = _login(client, "user4", "Pass1234!")
    effective = client.get(
        "/aris3/access-control/effective-permissions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert effective.status_code == 200
    permissions = {entry["key"]: entry for entry in effective.json()["permissions"]}
    assert permissions["USER_MANAGE"]["allowed"] is False
    assert permissions["USER_MANAGE"]["source"] == "user_override_deny"
    assert permissions["AUDIT_VIEW"]["allowed"] is True
    assert permissions["AUDIT_VIEW"]["source"] == "user_override_allow"
    assert permissions["STORE_VIEW"]["allowed"] is False
    assert permissions["STORE_VIEW"]["source"] == "tenant_policy_deny"

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.action == "access_control.user_override.update")
        .first()
    )
    assert event is not None
    assert event.result == "success"


def test_role_policy_requires_idempotency_key(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Idem")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin5", password="Pass1234!")

    token = _login(client, "admin5", "Pass1234!")
    response = client.put(
        f"/aris3/access-control/tenants/{tenant.id}/role-policies/USER",
        headers={"Authorization": f"Bearer {token}"},
        json={"allow": ["STORE_VIEW"], "deny": []},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"
