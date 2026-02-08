import uuid

import pytest

from app.aris3.core.context import RequestContext
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import PermissionCatalog, RoleTemplate, RoleTemplatePermission, Store, Tenant, User
from app.aris3.db.seed import DEFAULT_ROLE_TEMPLATES, run_seed
from app.aris3.services.access_control import AccessControlService


def _seed_defaults(db_session):
    run_seed(db_session)


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


@pytest.mark.parametrize("role_name", ["SUPERADMIN", "ADMIN", "MANAGER", "USER"])
def test_effective_permissions_for_roles(client, db_session, role_name):
    _seed_defaults(db_session)
    tenant, store = _create_tenant_store(db_session, name_suffix=role_name)
    _create_user(db_session, tenant=tenant, store=store, role=role_name, username=role_name.lower(), password="Pass1234!")

    token = _login(client, role_name.lower(), "Pass1234!")
    response = client.get(
        "/aris3/access-control/effective-permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == str(tenant.id)
    assert payload["store_id"] == str(store.id)
    assert payload["role"] == role_name

    allowed_expected = set(DEFAULT_ROLE_TEMPLATES[role_name])
    permission_map = {entry["key"]: entry for entry in payload["permissions"]}
    for key in DEFAULT_ROLE_TEMPLATES["SUPERADMIN"]:
        if key in allowed_expected:
            assert permission_map[key]["allowed"] is True
            assert permission_map[key]["source"] == "role_template"
        else:
            assert permission_map[key]["allowed"] is False
            assert permission_map[key]["source"] == "default_deny"


def test_effective_permissions_unauthorized(client):
    response = client.get("/aris3/access-control/effective-permissions")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_unknown_permission_denied(db_session):
    _seed_defaults(db_session)
    context = RequestContext(user_id="user", tenant_id="tenant", store_id=None, role="USER", trace_id="")
    service = AccessControlService(db_session)
    decision = service.evaluate_permission("UNKNOWN_PERMISSION", context)
    assert decision.allowed is False
    assert decision.source == "unknown_permission"


def test_explicit_deny_overrides_allow(db_session):
    _seed_defaults(db_session)
    context = RequestContext(user_id="user", tenant_id=None, store_id=None, role="USER", trace_id="")

    def deny_store_view(_context):
        return {"STORE_VIEW"}

    service = AccessControlService(db_session, deny_resolvers=[deny_store_view])
    decision = service.evaluate_permission("STORE_VIEW", context)
    assert decision.allowed is False
    assert decision.source == "explicit_deny"


def test_tenant_scope_safety(client, db_session):
    _seed_defaults(db_session)
    tenant_a, store_a = _create_tenant_store(db_session, name_suffix="A")
    tenant_b, _store_b = _create_tenant_store(db_session, name_suffix="B")

    permission = (
        db_session.query(PermissionCatalog).filter(PermissionCatalog.code == "AUDIT_VIEW").first()
    )
    role_template = RoleTemplate(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        name="MANAGER",
        description="Tenant B Manager",
        is_system=False,
    )
    db_session.add(role_template)
    db_session.flush()
    db_session.add(
        RoleTemplatePermission(role_template_id=role_template.id, permission_id=permission.id)
    )
    db_session.commit()

    _create_user(db_session, tenant=tenant_a, store=store_a, role="MANAGER", username="manager-a", password="Pass1234!")
    token = _login(client, "manager-a", "Pass1234!")

    response = client.get(
        "/aris3/access-control/effective-permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    permission_map = {entry["key"]: entry for entry in payload["permissions"]}
    assert permission_map["AUDIT_VIEW"]["allowed"] is False
    assert permission_map["AUDIT_VIEW"]["source"] == "default_deny"
