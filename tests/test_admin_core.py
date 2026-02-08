import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import (
    AuditEvent,
    Store,
    Tenant,
    User,
    UserPermissionOverride,
)
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


def test_admin_store_tenant_scope_and_idempotency(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="A")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="B")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin-a", password="Pass1234!")

    token = _login(client, "admin-a", "Pass1234!")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "store-create-1"}
    payload = {"name": "Tenant A Store"}

    response = client.post("/aris3/admin/stores", headers=headers, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["store"]["tenant_id"] == str(tenant_a.id)

    replay = client.post("/aris3/admin/stores", headers=headers, json=payload)
    assert replay.status_code == response.status_code
    assert replay.json() == body
    assert replay.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"

    list_response = client.get("/aris3/admin/stores", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    store_ids = {item["id"] for item in list_response.json()["stores"]}
    assert str(store_b.id) not in store_ids

    update_response = client.patch(
        f"/aris3/admin/stores/{store_b.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "store-update-1"},
        json={"name": "Denied"},
    )
    assert update_response.status_code == 403
    assert update_response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

    event = db_session.query(AuditEvent).filter(AuditEvent.action == "admin.store.create").first()
    assert event is not None
    assert event.result == "success"


def test_admin_user_actions_and_role_ceiling(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Actions")
    admin = _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin", password="Pass1234!")
    target = _create_user(db_session, tenant=tenant, store=store, role="USER", username="user", password="Pass1234!")

    token = _login(client, "admin", "Pass1234!")

    status_response = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-status-1"},
        json={"action": "set_status", "status": "SUSPENDED", "transaction_id": "txn-status-1"},
    )
    assert status_response.status_code == 200
    payload = status_response.json()["user"]
    assert payload["status"] == "suspended"
    assert payload["is_active"] is False

    role_response = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-role-1"},
        json={"action": "set_role", "role": "MANAGER", "transaction_id": "txn-role-1"},
    )
    assert role_response.status_code == 200
    assert role_response.json()["user"]["role"] == "MANAGER"

    reset_response = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-reset-1"},
        json={"action": "reset_password", "transaction_id": "txn-reset-1"},
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["user"]["must_change_password"] is True
    assert reset_response.json()["temporary_password"]

    db_session.add(
        UserPermissionOverride(
            tenant_id=tenant.id,
            user_id=admin.id,
            permission_code="STORE_VIEW",
            effect="deny",
        )
    )
    db_session.commit()

    ceiling_response = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-role-2"},
        json={"action": "set_role", "role": "ADMIN", "transaction_id": "txn-role-2"},
    )
    assert ceiling_response.status_code == 403
    assert ceiling_response.json()["code"] == "PERMISSION_DENIED"

    event = db_session.query(AuditEvent).filter(AuditEvent.action == "admin.user.reset_password").first()
    assert event is not None
    assert event.result == "success"
    assert event.event_metadata["target_user_id"] == str(target.id)


def test_admin_user_cross_tenant_denied(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="A2")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="B2")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin-a2", password="Pass1234!")
    user_b = _create_user(db_session, tenant=tenant_b, store=store_b, role="USER", username="user-b2", password="Pass1234!")

    token = _login(client, "admin-a2", "Pass1234!")
    response = client.post(
        f"/aris3/admin/users/{user_b.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-cross-1"},
        json={"action": "set_status", "status": "SUSPENDED", "transaction_id": "txn-cross-1"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"


def test_superadmin_can_manage_cross_tenant_user(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="SA-A")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="SA-B")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin-a3", password="Pass1234!")
    user_b = _create_user(db_session, tenant=tenant_b, store=store_b, role="USER", username="user-b3", password="Pass1234!")

    token = _login(client, "superadmin", "change-me")
    response = client.post(
        f"/aris3/admin/users/{user_b.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "superadmin-cross-1"},
        json={"action": "set_status", "status": "SUSPENDED", "transaction_id": "txn-sa-1"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["status"] == "suspended"


def test_variant_fields_settings_patch_and_audit(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Settings")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-settings", password="Pass1234!")

    token = _login(client, "admin-settings", "Pass1234!")
    get_response = client.get(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["var1_label"] is None

    patch_response = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "settings-1"},
        json={"var1_label": "Color", "var2_label": "Size"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["var1_label"] == "Color"
    assert patch_response.json()["var2_label"] == "Size"

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.action == "admin.settings.variant_fields.update")
        .first()
    )
    assert event is not None
    assert event.result == "success"


def test_admin_mutations_require_idempotency_key(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Idem")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-idem", password="Pass1234!")

    token = _login(client, "admin-idem", "Pass1234!")
    response = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {token}"},
        json={"var1_label": "Shade"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_admin_user_actions_idempotency_replay_and_conflict(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Idem-User")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-idem-user", password="Pass1234!")
    target = _create_user(db_session, tenant=tenant, store=store, role="USER", username="user-idem", password="Pass1234!")

    token = _login(client, "admin-idem-user", "Pass1234!")

    status_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-status-1"}
    status_payload = {"action": "set_status", "status": "SUSPENDED", "transaction_id": "txn-idem-1"}
    first_status = client.post(f"/aris3/admin/users/{target.id}/actions", headers=status_headers, json=status_payload)
    assert first_status.status_code == 200
    replay_status = client.post(f"/aris3/admin/users/{target.id}/actions", headers=status_headers, json=status_payload)
    assert replay_status.status_code == 200
    assert replay_status.json() == first_status.json()
    assert replay_status.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"
    conflict_status = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers=status_headers,
        json={"action": "set_status", "status": "ACTIVE", "transaction_id": "txn-idem-2"},
    )
    assert conflict_status.status_code == 409
    assert conflict_status.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

    role_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-role-1"}
    role_payload = {"action": "set_role", "role": "MANAGER", "transaction_id": "txn-idem-3"}
    first_role = client.post(f"/aris3/admin/users/{target.id}/actions", headers=role_headers, json=role_payload)
    assert first_role.status_code == 200
    replay_role = client.post(f"/aris3/admin/users/{target.id}/actions", headers=role_headers, json=role_payload)
    assert replay_role.status_code == 200
    assert replay_role.json() == first_role.json()
    conflict_role = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers=role_headers,
        json={"action": "set_role", "role": "USER", "transaction_id": "txn-idem-4"},
    )
    assert conflict_role.status_code == 409
    assert conflict_role.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

    reset_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-reset-1"}
    reset_payload = {"action": "reset_password", "transaction_id": "txn-idem-5"}
    first_reset = client.post(f"/aris3/admin/users/{target.id}/actions", headers=reset_headers, json=reset_payload)
    assert first_reset.status_code == 200
    replay_reset = client.post(f"/aris3/admin/users/{target.id}/actions", headers=reset_headers, json=reset_payload)
    assert replay_reset.status_code == 200
    assert replay_reset.json() == first_reset.json()
    conflict_reset = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers=reset_headers,
        json={"action": "reset_password", "temporary_password": "AltPass123", "transaction_id": "txn-idem-6"},
    )
    assert conflict_reset.status_code == 409
    assert conflict_reset.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
