import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


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
    body = response.json()
    assert "trace_id" in body
    return body["access_token"]


def test_success_schema_includes_trace_id_by_family(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Contract")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Contract")
    db_session.add_all([tenant, store])
    db_session.commit()
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-contract", password="Pass1234!")

    superadmin_token = _login(client, "superadmin", "change-me")
    admin_token = _login(client, "admin-contract", "Pass1234!")

    checks = [
        ("/aris3/admin/tenants", superadmin_token),
        ("/aris3/admin/stores", admin_token),
        ("/aris3/admin/users", admin_token),
        ("/aris3/admin/access-control/permission-catalog", superadmin_token),
        (f"/aris3/admin/settings/return-policy?tenant_id={tenant.id}", superadmin_token),
    ]
    for path, token in checks:
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert "trace_id" in body
        assert response.headers.get("X-Trace-Id")


def test_unauthorized_response_schema(client):
    response = client.get("/aris3/admin/tenants")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["code"] == "INVALID_TOKEN"
    assert "trace_id" in response.json()


def test_forbidden_response_schema(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Tenant F")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store F")
    db_session.add_all([tenant, store])
    db_session.commit()
    _create_user(db_session, tenant=tenant, store=store, role="USER", username="basic-user", password="Pass1234!")

    token = _login(client, "basic-user", "Pass1234!")
    response = client.get(
        "/aris3/admin/access-control/permission-catalog",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
    assert "trace_id" in response.json()


def test_not_found_response_schema(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    response = client.get(
        f"/aris3/admin/tenants/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    assert "trace_id" in response.json()


def test_conflict_response_schema_for_idempotency_reuse(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "same-key"}

    first = client.post("/aris3/admin/tenants", headers=headers, json={"name": "Tenant One"})
    assert first.status_code == 201

    second = client.post("/aris3/admin/tenants", headers=headers, json={"name": "Tenant Two"})
    assert second.status_code == 409
    assert second.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
    assert "trace_id" in second.json()


def test_create_tenant_regression_no_tenant_snapshot_name_error(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    response = client.post(
        "/aris3/admin/tenants",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-snapshot-regression"},
        json={"name": "Tenant Snapshot Regression"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["tenant"]["name"] == "Tenant Snapshot Regression"
    assert payload["tenant"]["status"] == "ACTIVE"
    assert "trace_id" in payload


def test_validation_error_schema_for_missing_idempotency_key(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    response = client.post(
        "/aris3/admin/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "No idempotency"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"]["errors"][0]["field"] == "Idempotency-Key"
    assert "trace_id" in body
