import uuid
from datetime import datetime

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


def test_stock_query_contract(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="contract")
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku="SKU-1",
            description="Blue Jacket",
            var1_value="Blue",
            var2_value="L",
            epc="EPC-1",
            location_code="LOC-1",
            pool="P1",
            status="RFID",
            location_is_vendible=True,
            image_asset_id=uuid.uuid4(),
            image_url="https://example.com/image.png",
            image_thumb_url="https://example.com/thumb.png",
            image_source="catalog",
            image_updated_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    token = _login(client, user.username, "Pass1234!")
    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"meta", "rows", "totals"}
    assert payload["meta"]["page"] == 1
    assert payload["meta"]["page_size"] == 50
    assert payload["rows"]

    row = payload["rows"][0]
    expected_fields = {
        "id",
        "tenant_id",
        "sku",
        "description",
        "var1_value",
        "var2_value",
        "epc",
        "location_code",
        "pool",
        "status",
        "location_is_vendible",
        "image_asset_id",
        "image_url",
        "image_thumb_url",
        "image_source",
        "image_updated_at",
        "cost_price",
        "suggested_price",
        "sale_price",
        "created_at",
        "updated_at",
    }
    assert set(row.keys()) == expected_fields
