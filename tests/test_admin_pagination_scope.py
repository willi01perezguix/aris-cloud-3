import uuid

from sqlalchemy import select

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


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


def _collect_all_pages(client, url: str, token: str, resource_key: str, limit: int):
    offset = 0
    collected = []
    while True:
        response = client.get(
            f"{url}{'&' if '?' in url else '?'}limit={limit}&offset={offset}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        page_items = payload[resource_key]
        pagination = payload["pagination"]
        assert pagination["limit"] == limit
        assert pagination["offset"] == offset
        assert pagination["count"] == len(page_items)
        collected.extend(page_items)
        if len(page_items) < limit:
            break
        offset += limit
    return collected


def test_admin_stores_global_superadmin_pagination_is_complete_and_stable(client, db_session):
    run_seed(db_session)

    # Build dataset > 200 stores across many tenants.
    for i in range(260):
        tenant = Tenant(id=uuid.uuid4(), name=f"Bulk Tenant {i:03d}")
        store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Bulk Store")
        db_session.add_all([tenant, store])
    db_session.commit()

    token = _login(client, "superadmin", "change-me")

    first_run = _collect_all_pages(
        client,
        "/aris3/admin/stores?sort_by=name&sort_order=asc",
        token,
        "stores",
        limit=200,
    )
    second_run = _collect_all_pages(
        client,
        "/aris3/admin/stores?sort_by=name&sort_order=asc",
        token,
        "stores",
        limit=200,
    )

    first_ids = [item["id"] for item in first_run]
    second_ids = [item["id"] for item in second_run]

    assert len(first_ids) > 200
    assert len(first_ids) == len(set(first_ids))
    assert first_ids == second_ids

    expected_total = db_session.execute(select(Store)).scalars().all()
    assert len(first_ids) == len(expected_total)


def test_admin_users_scope_and_pagination(client, db_session):
    run_seed(db_session)

    tenant_a, store_a = _create_tenant_store(db_session, suffix="A")
    tenant_b, store_b = _create_tenant_store(db_session, suffix="B")
    tenant_admin = _create_user(
        db_session,
        tenant=tenant_a,
        store=store_a,
        role="ADMIN",
        username="tenant-admin-pagination",
        password="Pass1234!",
    )

    for i in range(230):
        _create_user(
            db_session,
            tenant=tenant_a,
            store=store_a,
            role="USER",
            username=f"tenant-a-user-{i:03d}",
            password="Pass1234!",
        )
    for i in range(25):
        _create_user(
            db_session,
            tenant=tenant_b,
            store=store_b,
            role="USER",
            username=f"tenant-b-user-{i:03d}",
            password="Pass1234!",
        )

    superadmin_token = _login(client, "superadmin", "change-me")
    admin_token = _login(client, tenant_admin.username, "Pass1234!")

    # Superadmin global listing gets users from all tenants.
    all_users = _collect_all_pages(
        client,
        "/aris3/admin/users?sort_by=created_at&sort_order=asc",
        superadmin_token,
        "users",
        limit=200,
    )
    all_tenants = {item["tenant_id"] for item in all_users}
    assert str(tenant_a.id) in all_tenants
    assert str(tenant_b.id) in all_tenants

    # Tenant-admin sees only own tenant even if requesting another tenant.
    forbidden = client.get(
        f"/aris3/admin/users?tenant_id={tenant_b.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

    own_users = _collect_all_pages(
        client,
        f"/aris3/admin/users?tenant_id={tenant_a.id}&sort_by=username&sort_order=asc",
        admin_token,
        "users",
        limit=200,
    )
    own_tenants = {item["tenant_id"] for item in own_users}
    assert own_tenants == {str(tenant_a.id)}


def test_admin_invalid_sort_and_non_admin_smoke(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")

    invalid_sort = client.get(
        "/aris3/admin/stores?sort_by=bad_field",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert invalid_sort.status_code == 422
    payload = invalid_sort.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert "allowed" in payload["details"]

    health = client.get("/health")
    assert health.status_code == 200
