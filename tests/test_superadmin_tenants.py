import uuid

from app.aris3.core.config import settings
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


def test_superadmin_can_manage_tenants(client, db_session):
    run_seed(db_session)
    token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)

    create_response = client.post(
        "/aris3/admin/tenants",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-create-1"},
        json={"name": "Platform Tenant"},
    )
    assert create_response.status_code == 201
    tenant_payload = create_response.json()["tenant"]
    assert tenant_payload["status"] == "active"

    tenant_id = tenant_payload["id"]
    get_response = client.get(
        f"/aris3/admin/tenants/{tenant_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200

    update_response = client.patch(
        f"/aris3/admin/tenants/{tenant_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-update-1"},
        json={"name": "Platform Tenant Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["tenant"]["name"] == "Platform Tenant Updated"

    action_response = client.post(
        f"/aris3/admin/tenants/{tenant_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-action-1"},
        json={"action": "set_status", "status": "SUSPENDED"},
    )
    assert action_response.status_code == 200
    assert action_response.json()["tenant"]["status"] == "suspended"

    list_response = client.get(
        "/aris3/admin/tenants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    tenant_ids = {item["id"] for item in list_response.json()["tenants"]}
    assert tenant_id in tenant_ids

    event = db_session.query(AuditEvent).filter(AuditEvent.action == "admin.tenant.create").first()
    assert event is not None
    assert event.result == "success"


def test_non_superadmin_denied_on_tenants(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Denied")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-denied", password="Pass1234!")

    token = _login(client, "admin-denied", "Pass1234!")
    response = client.get(
        "/aris3/admin/tenants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_tenant_mutations_require_idempotency_key(client, db_session):
    run_seed(db_session)
    token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)

    create_response = client.post(
        "/aris3/admin/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Idem Tenant"},
    )
    assert create_response.status_code == 400
    assert create_response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    tenant = Tenant(name="Idem Tenant 2")
    db_session.add(tenant)
    db_session.commit()

    update_response = client.patch(
        f"/aris3/admin/tenants/{tenant.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Idem Tenant Updated"},
    )
    assert update_response.status_code == 400
    assert update_response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    action_response = client.post(
        f"/aris3/admin/tenants/{tenant.id}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "set_status", "status": "SUSPENDED"},
    )
    assert action_response.status_code == 400
    assert action_response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_superadmin_store_creation_requires_explicit_tenant_and_honors_precedence(client, db_session):
    run_seed(db_session)
    tenant_a, _ = _create_tenant_store(db_session, name_suffix="StoreTargetA")
    tenant_b, _ = _create_tenant_store(db_session, name_suffix="StoreTargetB")
    tenant_c, _ = _create_tenant_store(db_session, name_suffix="StoreTargetC")

    token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)

    missing_response = client.post(
        "/aris3/admin/stores",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "super-store-missing-tenant"},
        json={"name": "Missing Tenant Store"},
    )
    assert missing_response.status_code == 400
    assert missing_response.json()["code"] == "TENANT_ID_REQUIRED_FOR_SUPERADMIN"

    create_response = client.post(
        f"/aris3/admin/stores?tenant_id={tenant_b.id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "super-store-precedence",
            "X-Tenant-Id": str(tenant_c.id),
        },
        json={"name": "Super Store", "tenant_id": str(tenant_a.id)},
    )
    assert create_response.status_code == 201
    assert create_response.json()["store"]["tenant_id"] == str(tenant_a.id)
