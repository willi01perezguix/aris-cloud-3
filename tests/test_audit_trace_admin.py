import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import AuditEvent, Store, Tenant, User
from app.aris3.db.seed import run_seed


def _create_tenant_store(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    db_session.add_all([tenant, store])
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
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_create_store_audit_contains_trace_and_no_duplicate_on_replay(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, suffix="Audit")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-audit", password="Pass1234!")

    token = _login(client, "admin-audit", "Pass1234!")
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "audit-store-1",
        "X-Trace-ID": "trace-admin-audit-1",
    }

    first = client.post("/aris3/admin/stores", headers=headers, json={"name": "Audit Store"})
    assert first.status_code == 201
    assert first.headers.get("X-Trace-ID") == "trace-admin-audit-1"

    replay = client.post("/aris3/admin/stores", headers=headers, json={"name": "Audit Store"})
    assert replay.status_code == 201

    events = db_session.query(AuditEvent).filter(AuditEvent.action == "admin.store.create").all()
    assert len(events) == 1
    event = events[0]
    assert event.before_payload is None
    assert event.after_payload["name"] == "Audit Store"
    assert event.trace_id == "trace-admin-audit-1"
    assert event.event_metadata["actor_role"] == "ADMIN"
    assert event.event_metadata["effective_tenant_id"] == str(tenant.id)


def test_admin_error_responses_include_trace_id(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, suffix="TraceErr")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-trace", password="Pass1234!")

    token = _login(client, "admin-trace", "Pass1234!")
    response = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {token}", "X-Trace-ID": "trace-admin-error-1"},
        json={"var1_label": "Size"},
    )

    assert response.status_code == 400
    assert response.headers.get("X-Trace-ID") == "trace-admin-error-1"
    assert response.json()["trace_id"] == "trace-admin-error-1"
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"
