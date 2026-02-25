import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.aris3.core.error_catalog import ErrorCatalog
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


def _import_sku_payload(store_id: str) -> dict:
    return {
        "transaction_id": f"txn-sku-{uuid.uuid4()}",
        "lines": [
            {
                "sku": "SKU-1",
                "description": "Blue Jacket",
                "var1_value": "Blue",
                "var2_value": "L",
                "epc": None,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "PENDING",
                "location_is_vendible": True,
                "image_asset_id": str(uuid.uuid4()),
                "image_url": "https://example.com/image.png",
                "image_thumb_url": "https://example.com/thumb.png",
                "image_source": "catalog",
                "image_updated_at": datetime.utcnow().isoformat(),
                "qty": 1,
                "store_id": store_id,
            }
        ],
    }


def test_upload_image_allows_superadmin_and_admin(client, db_session, monkeypatch):
    run_seed(db_session)
    tenant, store, admin = _create_tenant_user(db_session, suffix="upload-admin", role="ADMIN")

    def fake_upload_image(*args, **kwargs):
        return SimpleNamespace(
            image_asset_id="asset-1",
            image_url="https://img.example.com/image.png",
            image_thumb_url="https://img.example.com/thumb.png",
            image_source="spaces",
            image_updated_at="2026-01-01T00:00:00Z",
        )

    monkeypatch.setattr(
        "app.aris3.routers.assets_images.SpacesImageService.upload_image",
        fake_upload_image,
    )

    admin_token = _login(client, admin.username, "Pass1234!")
    admin_response = client.post(
        "/aris3/assets/upload-image",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("photo.png", b"png-bytes", "image/png")},
        data={"tenant_id": str(tenant.id), "store_id": str(store.id)},
    )
    assert admin_response.status_code == 200
    admin_payload = admin_response.json()
    assert set(admin_payload) == {"image_asset_id", "image_url", "image_thumb_url", "image_source", "image_updated_at"}

    superadmin_token = _login(client, "superadmin", "change-me")
    superadmin_response = client.post(
        "/aris3/assets/upload-image",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        files={"file": ("photo.png", b"png-bytes", "image/png")},
        data={"tenant_id": str(tenant.id), "store_id": str(store.id)},
    )
    assert superadmin_response.status_code == 200
    superadmin_payload = superadmin_response.json()
    assert set(superadmin_payload) == {"image_asset_id", "image_url", "image_thumb_url", "image_source", "image_updated_at"}


@pytest.mark.parametrize("role", ["MANAGER", "USER", "CASHIER"])
def test_upload_image_denies_non_admin_roles(client, db_session, role):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, suffix=f"upload-{role.lower()}", role=role)
    token = _login(client, user.username, "Pass1234!")

    response = client.post(
        "/aris3/assets/upload-image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.png", b"png-bytes", "image/png")},
        data={"tenant_id": str(tenant.id), "store_id": str(store.id)},
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code


def test_import_sku_allows_superadmin_and_admin(client, db_session):
    run_seed(db_session)
    tenant, store, admin = _create_tenant_user(db_session, suffix="import-admin", role="ADMIN")

    admin_token = _login(client, admin.username, "Pass1234!")
    admin_response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": f"admin-{uuid.uuid4()}"},
        json=_import_sku_payload(str(store.id)),
    )
    assert admin_response.status_code == 201

    superadmin_token = _login(client, "superadmin", "change-me")
    superadmin_response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {superadmin_token}", "Idempotency-Key": f"super-{uuid.uuid4()}"},
        json={**_import_sku_payload(str(store.id)), "tenant_id": str(tenant.id)},
    )
    assert superadmin_response.status_code == 201


@pytest.mark.parametrize("role", ["MANAGER", "USER", "CASHIER"])
def test_import_sku_denies_non_admin_roles(client, db_session, role):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, suffix=f"import-{role.lower()}", role=role)
    token = _login(client, user.username, "Pass1234!")

    response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"deny-{role.lower()}-{uuid.uuid4()}"},
        json=_import_sku_payload(str(store.id)),
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code
