import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed
from app.aris3.core.config import settings


def _create_user(db_session, *, username: str, password: str, role: str = "ADMIN", status: str = "active", is_active: bool = True):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {username}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {username}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(password),
        role=role,
        status=status,
        is_active=is_active,
        must_change_password=False,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, store, user


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_auth_login_validation_error_uses_flat_error_envelope(client):
    response = client.post("/aris3/auth/login", json={"password": "missing-identifier"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["details"]["errors"], list)
    assert "trace_id" in body
    assert "detail" not in body


def test_change_password_patch_canonical_and_post_deprecated_alias(client, db_session):
    _create_user(db_session, username="pwd-admin", password="Pass1234!", role="ADMIN")
    token = _login(client, "pwd-admin", "Pass1234!")

    patch_response = client.patch(
        "/aris3/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Pass1234!", "new_password": "ChangeMe1234!"},
    )
    assert patch_response.status_code == 200
    assert "Deprecation" not in patch_response.headers

    post_response = client.post(
        "/aris3/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "ChangeMe1234!", "new_password": "Another1234!"},
    )
    assert post_response.status_code == 200
    assert post_response.headers.get("Deprecation") == "true"
    assert post_response.headers.get("Sunset") == "2026-06-30"


def test_admin_delete_not_found_and_conflict_include_details(client, db_session):
    _create_user(db_session, username="platform-super", password="Pass1234!", role="SUPERADMIN")
    super_token = _login(client, "platform-super", "Pass1234!")

    missing_store = str(uuid.uuid4())
    missing_response = client.delete(
        f"/aris3/admin/stores/{missing_store}",
        headers={"Authorization": f"Bearer {super_token}", "Idempotency-Key": "delete-missing-store"},
    )
    assert missing_response.status_code == 404
    missing_payload = missing_response.json()
    assert missing_payload["code"] == "RESOURCE_NOT_FOUND"
    assert missing_payload["details"]["path"] == f"/aris3/admin/stores/{missing_store}"

    tenant = Tenant(id=uuid.uuid4(), name="Tenant Conflict")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Conflict")
    db_session.add_all([tenant, store])
    db_session.commit()

    conflict_response = client.delete(
        f"/aris3/admin/tenants/{tenant.id}",
        headers={"Authorization": f"Bearer {super_token}", "Idempotency-Key": "delete-tenant-conflict"},
    )
    assert conflict_response.status_code == 409
    conflict_payload = conflict_response.json()
    assert conflict_payload["code"] == "CONFLICT"
    assert conflict_payload["details"]["dependencies"]["stores"] >= 1


def test_users_status_and_is_active_filters_are_consistent(client, db_session):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Users")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Users")
    active_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username="active-user",
        email="active-user@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        is_active=True,
        must_change_password=False,
    )
    suspended_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username="suspended-user",
        email="suspended-user@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="USER",
        status="suspended",
        is_active=False,
        must_change_password=False,
    )
    db_session.add_all([tenant, store, active_user, suspended_user])
    db_session.commit()

    run_seed(db_session)
    admin_token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)

    status_response = client.get(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"tenant_id": str(tenant.id), "status": "suspended"},
    )
    assert status_response.status_code == 200
    users = status_response.json()["users"]
    assert len(users) == 1
    assert users[0]["status"] == "SUSPENDED"
    assert users[0]["is_active"] is False

    active_response = client.get(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"tenant_id": str(tenant.id), "is_active": True},
    )
    assert active_response.status_code == 200
    assert all(item["is_active"] is True and item["status"] == "ACTIVE" for item in active_response.json()["users"])


def test_openapi_stores_docs_and_change_password_deprecation_and_health_ready_contract():
    from app.main import app

    schema = app.openapi()
    stores_get = schema["paths"]["/aris3/admin/stores"]["get"]
    params = {entry["name"]: entry for entry in stores_get["parameters"]}
    assert "tenant_id" in params
    assert "query_tenant_id" in params
    assert params["query_tenant_id"]["deprecated"] is True
    assert stores_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("StoreListResponse")

    patch_op = schema["paths"]["/aris3/auth/change-password"]["patch"]
    post_op = schema["paths"]["/aris3/auth/change-password"]["post"]
    assert patch_op.get("deprecated") is not True
    assert post_op.get("deprecated") is True

    health_schema = schema["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    ready_schema = schema["paths"]["/ready"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert health_schema["$ref"].endswith("ServiceHealthResponse")
    assert ready_schema["$ref"].endswith("ServiceHealthResponse")
    ready_503 = schema["paths"]["/ready"]["get"]["responses"]["503"]["content"]["application/json"]["schema"]
    assert ready_503["$ref"].endswith("ApiErrorResponse")

    users_get = schema["paths"]["/aris3/admin/users"]["get"]
    users_params = {entry["name"]: entry for entry in users_get["parameters"]}
    assert users_params["is_active"]["deprecated"] is True

    token_post = schema["paths"]["/aris3/auth/token"]["post"]
    assert token_post.get("deprecated") is True
    token_description = token_post.get("description") or ""
    assert "Compatibility endpoint" in token_description
    assert "POST /aris3/auth/login" in token_description
