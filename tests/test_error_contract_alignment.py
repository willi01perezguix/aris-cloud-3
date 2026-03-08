import uuid

from app.aris3.db.models import Transfer
from app.aris3.db.seed import run_seed
from tests.test_admin_core import _create_tenant_store, _create_user, _login


def test_422_validation_error_contract_includes_trace_id(client):
    response = client.post("/aris3/auth/login", json={})
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "Validation error"
    assert isinstance(payload["details"]["errors"], list)
    first = payload["details"]["errors"][0]
    assert {"field", "message", "type"}.issubset(first.keys())
    assert payload["trace_id"].startswith("trace-")


def test_401_uses_standard_body_and_www_authenticate(client):
    response = client.get("/aris3/me")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    payload = response.json()
    assert payload["code"] == "INVALID_TOKEN"
    assert payload["message"] == "Invalid token"
    assert payload["trace_id"]


def test_403_and_404_follow_standard_error_shape(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="err-shape")
    _create_user(db_session, tenant=tenant, store=store, role="USER", username="deny-user", password="Pass1234!")
    user_token = _login(client, "deny-user", "Pass1234!")

    denied = client.get("/aris3/admin/tenants", headers={"Authorization": f"Bearer {user_token}"})
    assert denied.status_code == 403
    assert denied.json()["code"] == "PERMISSION_DENIED"
    assert denied.json()["message"] == "Permission denied"
    assert denied.json()["trace_id"]

    superadmin_token = _login(client, "superadmin", "change-me")
    not_found = client.get(
        f"/aris3/admin/tenants/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert not_found.status_code == 404
    assert not_found.json()["code"] == "RESOURCE_NOT_FOUND"
    assert not_found.json()["details"]["path"].startswith("/aris3/admin/tenants/")
    assert not_found.json()["message"] == "Tenant not found"
    assert not_found.json()["trace_id"]



def test_409_http_exception_uses_conflict_code(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="409")
    target = _create_user(db_session, tenant=tenant, store=store, role="USER", username="user-409", password="Pass1234!")
    db_session.add(Transfer(tenant_id=tenant.id, origin_store_id=store.id, destination_store_id=store.id, created_by_user_id=target.id))
    db_session.commit()

    token = _login(client, "superadmin", "change-me")
    response = client.delete(
        f"/aris3/admin/users/{target.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-user-409"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
    assert response.json()["message"] == "Resource conflict"
    assert response.json()["trace_id"]


def test_status_lowercase_is_normalized_to_uppercase(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")

    created = client.post(
        "/aris3/admin/tenants",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-lc"},
        json={"name": "Tenant Lowercase"},
    )
    tenant_id = created.json()["tenant"]["id"]

    updated = client.post(
        f"/aris3/admin/tenants/{tenant_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-lc-action"},
        json={"action": "set_status", "status": "suspended"},
    )
    assert updated.status_code == 200
    assert updated.json()["tenant"]["status"] == "SUSPENDED"


def test_create_store_body_and_query_tenant_mismatch_returns_422(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant_a, _ = _create_tenant_store(db_session, name_suffix="qa")
    tenant_b, _ = _create_tenant_store(db_session, name_suffix="qb")

    response = client.post(
        f"/aris3/admin/stores?query_tenant_id={tenant_b.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "store-mismatch"},
        json={"name": "Mismatch", "tenant_id": str(tenant_a.id)},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["trace_id"]
