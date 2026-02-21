import uuid

from app.aris3.core.config import settings
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_user(db_session, *, tenant_id, store_id, username: str, role: str = "USER", status: str = "active"):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role=role,
        status=status,
        must_change_password=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_admin_list_tenants_supports_filters_and_pagination(client, db_session):
    run_seed(db_session)
    token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)

    t1 = Tenant(id=uuid.uuid4(), name="Acme Search", status="active")
    t2 = Tenant(id=uuid.uuid4(), name="Acme Suspended", status="suspended")
    db_session.add_all([t1, t2])
    db_session.commit()

    response = client.get(
        "/aris3/admin/tenants?status=active&search=Acme&limit=1&offset=0&sort_by=name&sort_order=asc",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenants"][0]["name"] == "Acme Search"
    assert payload["pagination"]["limit"] == 1
    assert payload["pagination"]["count"] == 1
    assert payload["pagination"]["total"] >= 1


def test_admin_list_stores_supports_tenant_filter_and_search(client, db_session):
    run_seed(db_session)
    token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)

    tenant_a = Tenant(id=uuid.uuid4(), name="Stores A", status="active")
    tenant_b = Tenant(id=uuid.uuid4(), name="Stores B", status="active")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    store_a = Store(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Main Search Store")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant_b.id, name="Other Tenant Store")
    db_session.add_all([store_a, store_b])
    db_session.commit()

    response = client.get(
        f"/aris3/admin/stores?tenant_id={tenant_a.id}&search=Main&limit=20&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["stores"]) == 1
    assert payload["stores"][0]["id"] == str(store_a.id)
    assert payload["pagination"]["total"] == 1


def test_admin_list_users_supports_filters_search_and_sort(client, db_session):
    run_seed(db_session)

    tenant = Tenant(id=uuid.uuid4(), name="User Tenant", status="active")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store B")
    db_session.add_all([tenant, store_a, store_b])
    db_session.commit()

    _create_user(db_session, tenant_id=tenant.id, store_id=store_a.id, username="admin-filter", role="ADMIN")
    _create_user(db_session, tenant_id=tenant.id, store_id=store_a.id, username="juan.manager", role="MANAGER", status="active")
    _create_user(db_session, tenant_id=tenant.id, store_id=store_b.id, username="other.user", role="USER", status="suspended")

    token = _login(client, "admin-filter", "Pass1234!")
    response = client.get(
        f"/aris3/admin/users?store_id={store_a.id}&role=MANAGER&status=active&search=juan&limit=10&offset=0&sort_by=username&sort_order=asc",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["users"]) == 1
    assert payload["users"][0]["username"] == "juan.manager"
    assert payload["pagination"]["count"] == 1


def test_admin_list_users_rejects_invalid_sort_by(client, db_session):
    run_seed(db_session)
    tenant = Tenant(id=uuid.uuid4(), name="Sort Tenant", status="active")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store")
    db_session.add_all([tenant, store])
    db_session.commit()
    _create_user(db_session, tenant_id=tenant.id, store_id=store.id, username="admin-sort", role="ADMIN")

    token = _login(client, "admin-sort", "Pass1234!")
    response = client.get(
        "/aris3/admin/users?sort_by=drop_table",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
