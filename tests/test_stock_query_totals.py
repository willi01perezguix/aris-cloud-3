import uuid

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


def test_stock_query_totals(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="totals")
    db_session.add_all(
        [
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, status="RFID", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, status="RFID", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, status="PENDING", location_is_vendible=True),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, status="PENDING", location_is_vendible=False),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, status="MISSING", location_is_vendible=True),
        ]
    )
    db_session.commit()

    token = _login(client, user.username, "Pass1234!")
    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    totals = response.json()["totals"]
    assert totals["total_rfid"] == 2
    assert totals["total_pending"] == 1
    assert totals["total_units"] == totals["total_rfid"] + totals["total_pending"]
