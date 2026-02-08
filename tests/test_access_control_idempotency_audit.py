import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import AuditEvent, Store, Tenant, User
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


def test_admin_idempotency_replay_conflict_and_audit(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="IdemAudit")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-i", password="Pass1234!")

    token = _login(client, "admin-i", "Pass1234!")
    payload = {"allow": ["AUDIT_VIEW"], "deny": [], "transaction_id": "txn-i-1"}
    response = client.put(
        "/aris3/admin/access-control/tenant-role-policies/USER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json=payload,
    )
    assert response.status_code == 200

    replay = client.put(
        "/aris3/admin/access-control/tenant-role-policies/USER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"

    conflict = client.put(
        "/aris3/admin/access-control/tenant-role-policies/USER",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json={"allow": ["AUDIT_VIEW"], "deny": ["STORE_VIEW"], "transaction_id": "txn-i-2"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.action == "access_control.tenant_role_policy.update")
        .first()
    )
    assert event is not None
    assert event.result == "success"
