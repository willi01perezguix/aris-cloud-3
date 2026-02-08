import uuid

from app.aris3.core.config import settings
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_user(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"admin-{suffix}",
        email=f"admin-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, user


def test_stock_query_tenant_scope(client, db_session):
    run_seed(db_session)
    tenant_a, user_a = _create_tenant_user(db_session, suffix="scope-a")
    tenant_b, _user_b = _create_tenant_user(db_session, suffix="scope-b")
    db_session.add_all(
        [
            StockItem(id=uuid.uuid4(), tenant_id=tenant_a.id, sku="SKU-A", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant_b.id, sku="SKU-B", location_is_vendible=True),
        ]
    )
    db_session.commit()

    token = _login(client, user_a.username, "Pass1234!")
    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert {row["sku"] for row in rows} == {"SKU-A"}

    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"tenant_id": str(tenant_b.id)},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

    super_token = _login(client, settings.SUPERADMIN_USERNAME, settings.SUPERADMIN_PASSWORD)
    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TENANT_SCOPE_REQUIRED"

    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {super_token}"},
        params={"tenant_id": str(tenant_b.id)},
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert {row["sku"] for row in rows} == {"SKU-B"}
