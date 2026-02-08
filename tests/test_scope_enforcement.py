import uuid

import pytest

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import enforce_store_scope, enforce_tenant_scope
from app.aris3.core.security import TokenData
from app.aris3.db.models import Store, Tenant


def _token_data(**overrides):
    data = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "store_id": None,
        "role": "USER",
        "status": "active",
        "is_active": True,
        "must_change_password": False,
        "email": "user@example.com",
        "username": "user",
    }
    data.update(overrides)
    return TokenData(**data)


def test_enforce_tenant_scope_blocks_cross_tenant():
    token_data = _token_data(tenant_id=str(uuid.uuid4()))
    other_tenant_id = str(uuid.uuid4())

    with pytest.raises(AppError) as exc:
        enforce_tenant_scope(token_data, other_tenant_id)
    assert exc.value.error == ErrorCatalog.CROSS_TENANT_ACCESS_DENIED


def test_enforce_store_scope_blocks_store_mismatch(db_session):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant A")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store A")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store B")
    db_session.add_all([tenant, store_a, store_b])
    db_session.commit()

    token_data = _token_data(
        tenant_id=str(tenant.id),
        store_id=str(store_a.id),
        role="USER",
    )

    with pytest.raises(AppError) as exc:
        enforce_store_scope(token_data, str(store_b.id), db_session)
    assert exc.value.error == ErrorCatalog.STORE_SCOPE_MISMATCH
