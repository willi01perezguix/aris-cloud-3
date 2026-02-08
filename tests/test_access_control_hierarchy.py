import uuid

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


def test_access_control_hierarchy_precedence_and_deny_wins(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Hierarchy")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-h", password="Pass1234!")
    user = _create_user(
        db_session,
        tenant=tenant,
        store=store,
        role="MANAGER",
        username="user-h",
        password="Pass1234!",
    )

    token = _login(client, "admin-h", "Pass1234!")
    tenant_policy = {"allow": ["AUDIT_VIEW"], "deny": ["USER_MANAGE"], "transaction_id": "txn-h-1"}
    response = client.put(
        "/aris3/admin/access-control/tenant-role-policies/MANAGER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-h-1"},
        json=tenant_policy,
    )
    assert response.status_code == 200

    store_policy = {
        "allow": ["USER_MANAGE"],
        "deny": ["AUDIT_VIEW"],
        "transaction_id": "txn-h-2",
    }
    response = client.put(
        f"/aris3/admin/access-control/store-role-policies/{store.id}/MANAGER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "store-h-1"},
        json=store_policy,
    )
    assert response.status_code == 200

    override_payload = {
        "allow": ["USER_MANAGE", "AUDIT_VIEW"],
        "transaction_id": "txn-h-3",
    }
    response = client.patch(
        f"/aris3/admin/access-control/user-overrides/{user.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "override-h-1"},
        json=override_payload,
    )
    assert response.status_code == 200

    effective = client.get(
        f"/aris3/admin/access-control/effective-permissions?user_id={user.id}&store_id={store.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert effective.status_code == 200
    payload = effective.json()
    permissions = {entry["key"]: entry for entry in payload["permissions"]}
    assert permissions["USER_MANAGE"]["allowed"] is False
    assert permissions["USER_MANAGE"]["source"] == "tenant_policy_deny"
    assert permissions["AUDIT_VIEW"]["allowed"] is False
    assert permissions["AUDIT_VIEW"]["source"] == "store_policy_deny"
    assert permissions["STORE_VIEW"]["allowed"] is True
    assert permissions["STORE_VIEW"]["source"] == "role_template"
    assert set(payload["denies_applied"]) == {"AUDIT_VIEW", "USER_MANAGE"}
    assert payload["subject"]["user_id"] == str(user.id)
    assert "MANAGER" == payload["subject"]["role"]
    assert payload["sources_trace"]["tenant"]["deny"] == ["USER_MANAGE"]
    assert payload["sources_trace"]["store"]["deny"] == ["AUDIT_VIEW"]
