import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import (
    AuditEvent,
    Store,
    Tenant,
    Transfer,
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
    cross_tenant_response = client.post(
        f"/aris3/admin/stores?query_tenant_id={tenant_b.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "store-create-cross-tenant"},
        json={"name": "Tenant A Store", "tenant_id": str(tenant_b.id)},
    )
    assert cross_tenant_response.status_code == 403
    assert cross_tenant_response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "store-create-1"}
    response = client.post("/aris3/admin/stores", headers=headers, json={"name": "Tenant A Store"})
    assert response.status_code == 201
    body = response.json()
    assert body["store"]["tenant_id"] == str(tenant_a.id)

    replay = client.post("/aris3/admin/stores", headers=headers, json={"name": "Tenant A Store"})
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




def test_create_user_superadmin_derives_tenant_from_store(client, db_session):
    run_seed(db_session)
    tenant_target, store_target = _create_tenant_store(db_session, name_suffix="SA-Create")

    token = _login(client, "superadmin", "change-me")
    response = client.post(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-create-superadmin-1"},
        json={
            "username": "sa-created-user",
            "email": "sa-created-user@example.com",
            "password": "Pass1234!",
            "role": "USER",
            "store_id": str(store_target.id),
        },
    )

    assert response.status_code == 201
    payload = response.json()["user"]
    assert payload["store_id"] == str(store_target.id)
    assert payload["tenant_id"] == str(tenant_target.id)


def test_create_user_tenant_admin_same_tenant_store(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Tenant-Scoped")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="tenant-admin", password="Pass1234!")

    token = _login(client, "tenant-admin", "Pass1234!")
    response = client.post(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-create-admin-1"},
        json={
            "username": "tenant-scoped-user",
            "email": "tenant-scoped-user@example.com",
            "password": "Pass1234!",
            "role": "USER",
            "store_id": str(store.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["tenant_id"] == str(tenant.id)


def test_create_user_tenant_admin_cross_tenant_store_denied(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="Tenant-A")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="Tenant-B")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="tenant-admin-cross", password="Pass1234!")

    token = _login(client, "tenant-admin-cross", "Pass1234!")
    response = client.post(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-create-cross-tenant-1"},
        json={
            "username": "cross-tenant-user",
            "email": "cross-tenant-user@example.com",
            "password": "Pass1234!",
            "role": "USER",
            "store_id": str(store_b.id),
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "TENANT_STORE_MISMATCH"


def test_create_user_store_not_found_returns_404(client, db_session):
    run_seed(db_session)

    token = _login(client, "superadmin", "change-me")
    response = client.post(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-create-missing-store-1"},
        json={
            "username": "missing-store-user",
            "email": "missing-store-user@example.com",
            "password": "Pass1234!",
            "role": "USER",
            "store_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "STORE_NOT_FOUND"


def test_create_user_store_id_required_returns_422(client, db_session):
    run_seed(db_session)

    token = _login(client, "superadmin", "change-me")
    response = client.post(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-create-missing-store-id-1"},
        json={
            "username": "missing-store-id-user",
            "email": "missing-store-id-user@example.com",
            "password": "Pass1234!",
            "role": "USER",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_user_payload_tenant_id_mismatch_returns_422(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="Payload-Mismatch-A")
    tenant_b, _store_b = _create_tenant_store(db_session, name_suffix="Payload-Mismatch-B")

    token = _login(client, "superadmin", "change-me")
    response = client.post(
        "/aris3/admin/users",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "user-create-tenant-mismatch-1"},
        json={
            "username": "payload-tenant-mismatch-user",
            "email": "payload-tenant-mismatch-user@example.com",
            "password": "Pass1234!",
            "role": "USER",
            "store_id": str(store_a.id),
            "tenant_id": str(tenant_b.id),
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"]["store_tenant_id"] == str(tenant_a.id)

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


def test_manager_store_scope_user_actions_denied_other_store(client, db_session):
    run_seed(db_session)
    tenant, store_a = _create_tenant_store(db_session, name_suffix="Mgr-Scope-A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Mgr-Scope-B")
    db_session.add(store_b)
    db_session.commit()

    _create_user(db_session, tenant=tenant, store=store_a, role="MANAGER", username="manager-scope", password="Pass1234!")
    target = _create_user(db_session, tenant=tenant, store=store_b, role="USER", username="user-other-store", password="Pass1234!")

    token = _login(client, "manager-scope", "Pass1234!")
    response = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "mgr-scope-denied-1"},
        json={"action": "set_status", "status": "SUSPENDED", "transaction_id": "txn-mgr-denied-1"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "STORE_SCOPE_MISMATCH"


def test_manager_store_scope_user_actions_allowed_same_store(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Mgr-Scope-Same")
    _create_user(db_session, tenant=tenant, store=store, role="MANAGER", username="manager-same-store", password="Pass1234!")
    target = _create_user(db_session, tenant=tenant, store=store, role="USER", username="user-same-store", password="Pass1234!")

    token = _login(client, "manager-same-store", "Pass1234!")
    response = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "mgr-scope-allow-1"},
        json={"action": "set_status", "status": "SUSPENDED", "transaction_id": "txn-mgr-allow-1"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["status"] == "suspended"


def test_admin_user_actions_tenant_wide_allowed_same_tenant(client, db_session):
    run_seed(db_session)
    tenant, store_a = _create_tenant_store(db_session, name_suffix="Admin-Tenant-A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Admin-Tenant-B")
    db_session.add(store_b)
    db_session.commit()

    _create_user(db_session, tenant=tenant, store=store_a, role="ADMIN", username="admin-tenant-wide", password="Pass1234!")
    target = _create_user(db_session, tenant=tenant, store=store_b, role="USER", username="user-tenant-wide", password="Pass1234!")

    token = _login(client, "admin-tenant-wide", "Pass1234!")
    response = client.post(
        f"/aris3/admin/users/{target.id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "admin-tenant-wide-1"},
        json={"action": "set_status", "status": "SUSPENDED", "transaction_id": "txn-admin-tenant-1"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["status"] == "suspended"


def test_superadmin_user_actions_cross_tenant_allowed(client, db_session):
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


def test_superadmin_can_manage_cross_tenant_user(client, db_session):
    test_superadmin_user_actions_cross_tenant_allowed(client, db_session)


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


def test_variant_fields_tenant_scope_rules_for_tenant_admin_and_superadmin(client, db_session):
    run_seed(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="Variant-A")
    tenant_b, store_b = _create_tenant_store(db_session, name_suffix="Variant-B")
    _create_user(db_session, tenant=tenant_a, store=store_a, role="ADMIN", username="admin-variant-a", password="Pass1234!")

    tenant_admin_token = _login(client, "admin-variant-a", "Pass1234!")

    tenant_get = client.get(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {tenant_admin_token}"},
    )
    assert tenant_get.status_code == 200

    tenant_patch = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {tenant_admin_token}", "Idempotency-Key": "variant-tenant-admin-1"},
        json={"var1_label": "Talla"},
    )
    assert tenant_patch.status_code == 200
    assert tenant_patch.json()["var1_label"] == "Talla"

    tenant_scope_mismatch = client.patch(
        f"/aris3/admin/settings/variant-fields?tenant_id={tenant_b.id}",
        headers={"Authorization": f"Bearer {tenant_admin_token}", "Idempotency-Key": "variant-tenant-admin-2"},
        json={"var2_label": "Color"},
    )
    assert tenant_scope_mismatch.status_code == 403
    assert tenant_scope_mismatch.json()["code"] == "TENANT_SCOPE_MISMATCH"

    superadmin_token = _login(client, "superadmin", "change-me")

    superadmin_get_missing_tenant = client.get(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert superadmin_get_missing_tenant.status_code == 400
    assert superadmin_get_missing_tenant.json()["code"] == "SUPERADMIN_REQUIRES_TENANT_ID_FOR_VARIANT_FIELDS"

    superadmin_patch_missing_tenant = client.patch(
        "/aris3/admin/settings/variant-fields",
        headers={"Authorization": f"Bearer {superadmin_token}", "Idempotency-Key": "variant-superadmin-1"},
        json={"var1_label": "Material"},
    )
    assert superadmin_patch_missing_tenant.status_code == 400
    assert superadmin_patch_missing_tenant.json()["code"] == "SUPERADMIN_REQUIRES_TENANT_ID_FOR_VARIANT_FIELDS"

    superadmin_get = client.get(
        f"/aris3/admin/settings/variant-fields?tenant_id={tenant_a.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert superadmin_get.status_code == 200
    assert superadmin_get.json()["var1_label"] == "Talla"

    superadmin_patch = client.patch(
        f"/aris3/admin/settings/variant-fields?tenant_id={tenant_a.id}",
        headers={"Authorization": f"Bearer {superadmin_token}", "Idempotency-Key": "variant-superadmin-2"},
        json={"var2_label": "Acabado"},
    )
    assert superadmin_patch.status_code == 200
    assert superadmin_patch.json()["var2_label"] == "Acabado"

    persisted = client.get(
        f"/aris3/admin/settings/variant-fields?tenant_id={tenant_a.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert persisted.status_code == 200
    assert persisted.json()["var1_label"] == "Talla"
    assert persisted.json()["var2_label"] == "Acabado"

    superadmin_not_found = client.get(
        f"/aris3/admin/settings/variant-fields?tenant_id={uuid.uuid4()}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert superadmin_not_found.status_code == 404
    assert superadmin_not_found.json()["code"] == "TENANT_NOT_FOUND"


def test_variant_fields_change_does_not_modify_stock_contract_var_fields():
    from app.main import app

    stock_row = app.openapi()["components"]["schemas"]["StockRow"]["properties"]
    assert "var1_value" in stock_row
    assert "var2_value" in stock_row
    assert "var1_label" not in stock_row
    assert "var2_label" not in stock_row


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



def test_superadmin_can_delete_user_with_idempotency_replay(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Delete-User")
    target = _create_user(db_session, tenant=tenant, store=store, role="USER", username="delete-user", password="Pass1234!")
    target_id = str(target.id)

    token = _login(client, "superadmin", "change-me")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-user-1"}

    response = client.delete(f"/aris3/admin/users/{target_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    replay = client.delete(f"/aris3/admin/users/{target_id}", headers=headers)
    assert replay.status_code == 200
    assert replay.json() == response.json()
    assert replay.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"

    db_session.expire_all()
    assert db_session.get(User, target_id) is None


def test_delete_user_requires_superadmin_and_valid_token(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Delete-User-Auth")
    _create_user(db_session, tenant=tenant, store=store, role="ADMIN", username="admin-delete", password="Pass1234!")
    target = _create_user(db_session, tenant=tenant, store=store, role="USER", username="user-delete", password="Pass1234!")

    admin_token = _login(client, "admin-delete", "Pass1234!")
    forbidden = client.delete(
        f"/aris3/admin/users/{target.id}",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "delete-user-auth-1"},
    )
    assert forbidden.status_code == 403

    unauthorized = client.delete(
        f"/aris3/admin/users/{target.id}",
        headers={"Authorization": "Bearer invalid.token", "Idempotency-Key": "delete-user-auth-2"},
    )
    assert unauthorized.status_code == 401


def test_delete_user_conflict_with_critical_dependencies(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Delete-User-Conflict")
    target = _create_user(db_session, tenant=tenant, store=store, role="USER", username="user-conflict", password="Pass1234!")
    db_session.add(
        Transfer(
            tenant_id=tenant.id,
            origin_store_id=store.id,
            destination_store_id=store.id,
            created_by_user_id=target.id,
        )
    )
    db_session.commit()

    token = _login(client, "superadmin", "change-me")
    response = client.delete(
        f"/aris3/admin/users/{target.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-user-conflict-1"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
    assert response.json()["message"] == "Cannot delete user with critical dependencies"
    assert response.json()["details"]["dependencies"]["transfers"] >= 1
    assert response.json()["trace_id"]


def test_superadmin_delete_store_success_and_not_found(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Delete-Store")
    store_id = str(store.id)
    token = _login(client, "superadmin", "change-me")

    response = client.delete(
        f"/aris3/admin/stores/{store_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-store-1"},
    )
    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Store, store_id) is None

    missing = client.delete(
        f"/aris3/admin/stores/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-store-2"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"
    assert missing.json()["trace_id"]


def test_admin_validation_error_uses_standard_envelope(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")

    response = client.post(
        "/aris3/admin/stores",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "admin-validation-envelope-1"},
        json={},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["details"]["errors"]
    assert response.json()["trace_id"]


def test_delete_store_conflict_with_dependencies(client, db_session):
    run_seed(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix="Delete-Store-Conflict")
    _create_user(db_session, tenant=tenant, store=store, role="USER", username="user-store-dep", password="Pass1234!")

    token = _login(client, "superadmin", "change-me")
    response = client.delete(
        f"/aris3/admin/stores/{store.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-store-conflict-1"},
    )
    assert response.status_code == 409
    assert response.json()["message"] == "Cannot delete store with active dependencies"
    assert response.json()["details"]["dependencies"]["users"] >= 1


def test_delete_tenant_success_conflict_and_not_found(client, db_session):
    run_seed(db_session)
    clean_tenant = Tenant(id=uuid.uuid4(), name="Delete Tenant Clean")
    clean_tenant_id = str(clean_tenant.id)
    db_session.add(clean_tenant)
    db_session.commit()

    token = _login(client, "superadmin", "change-me")

    success = client.delete(
        f"/aris3/admin/tenants/{clean_tenant_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-tenant-1"},
    )
    assert success.status_code == 200
    db_session.expire_all()
    assert db_session.get(Tenant, clean_tenant_id) is None

    tenant_dep, store_dep = _create_tenant_store(db_session, name_suffix="Delete-Tenant-Conflict")
    _create_user(db_session, tenant=tenant_dep, store=store_dep, role="USER", username="user-tenant-dep", password="Pass1234!")
    conflict = client.delete(
        f"/aris3/admin/tenants/{tenant_dep.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-tenant-2"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["message"] == "Cannot delete tenant with active dependencies"
    assert conflict.json()["details"]["dependencies"]["stores"] >= 1

    missing = client.delete(
        f"/aris3/admin/tenants/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-tenant-3"},
    )
    assert missing.status_code == 404
