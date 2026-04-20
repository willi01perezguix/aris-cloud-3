import uuid
from datetime import datetime
from types import SimpleNamespace

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import SkuImage, StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_user(db_session, *, suffix: str, role: str = "ADMIN"):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"user-{suffix}",
        email=f"user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role=role,
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, store, user


def test_catalog_images_returns_image_urls(client, db_session):
    run_seed(db_session)
    tenant, _store, admin = _create_tenant_user(db_session, suffix="catalog-images")
    sku = "SKU-IMG-1"
    asset_id = uuid.uuid4()
    db_session.add(
        SkuImage(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku=sku,
            asset_id=asset_id,
            file_hash=None,
            is_primary=True,
            sort_order=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    token = _login(client, admin.username, "Pass1234!")
    response = client.get(
        f"/aris3/catalog/sku/{sku}/images",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["asset_id"] == str(asset_id)
    assert payload[0]["is_primary"] is True
    assert payload[0]["image_url"]
    assert payload[0]["image_thumb_url"]


def test_stock_query_populates_catalog_image_urls(client, db_session):
    run_seed(db_session)
    tenant, store, admin = _create_tenant_user(db_session, suffix="stock-images")
    sku = "SKU-IMG-2"
    asset_id = uuid.uuid4()

    db_session.add(
        SkuImage(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku=sku,
            asset_id=asset_id,
            file_hash=None,
            is_primary=True,
            sort_order=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            store_id=store.id,
            sku=sku,
            description="SKU with image",
            status="PENDING",
            location_is_vendible=True,
            image_asset_id=asset_id,
            image_url=None,
            image_thumb_url=None,
            image_source=None,
            image_updated_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    token = _login(client, admin.username, "Pass1234!")
    response = client.get(
        "/aris3/stock",
        params={"scope": "self"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert row["image_asset_id"] == str(asset_id)
    assert row["image_url"]
    assert row["image_thumb_url"]
    assert row["image_thumb_url"] == row["image_url"]
    assert row["image_source"] == "catalog"


def test_asset_content_endpoint_serves_authorized_bytes(client, db_session, monkeypatch):
    run_seed(db_session)
    tenant, _store, admin = _create_tenant_user(db_session, suffix="asset-content")

    def _fake_download_image_by_asset_id(*_args, **_kwargs):
        return SimpleNamespace(content=b"fake-image-bytes", content_type="image/png", object_key="aris3/images/x.png")

    monkeypatch.setattr(
        "app.aris3.routers.assets_images.SpacesImageService.download_image_by_asset_id",
        _fake_download_image_by_asset_id,
    )

    token = _login(client, admin.username, "Pass1234!")
    asset_id = str(uuid.uuid4())
    response = client.get(
        f"/aris3/assets/{asset_id}/content",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == b"fake-image-bytes"


def test_asset_content_endpoint_rejects_cross_tenant_access(client, db_session, monkeypatch):
    run_seed(db_session)
    tenant_a, _store_a, admin_a = _create_tenant_user(db_session, suffix="asset-a")
    tenant_b, _store_b, _admin_b = _create_tenant_user(db_session, suffix="asset-b")

    def _fake_download_image_by_asset_id(*_args, **_kwargs):
        return SimpleNamespace(content=b"fake-image-bytes", content_type="image/png", object_key="aris3/images/x.png")

    monkeypatch.setattr(
        "app.aris3.routers.assets_images.SpacesImageService.download_image_by_asset_id",
        _fake_download_image_by_asset_id,
    )

    token_a = _login(client, admin_a.username, "Pass1234!")
    response = client.get(
        f"/aris3/assets/{uuid.uuid4()}/content",
        params={"tenant_id": str(tenant_b.id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"
    assert str(tenant_a.id) != str(tenant_b.id)
