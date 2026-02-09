from datetime import date

import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from tests.pos_sales_helpers import login, seed_defaults


def _create_tenant_store_user(db_session, *, suffix: str, role: str):
    tenant_id = uuid.uuid4()
    tenant = Tenant(id=tenant_id, name=f"Tenant {suffix}")
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


def test_exports_cross_tenant_denied(client, db_session):
    seed_defaults(db_session)
    _tenant_a, store_a, user_a = _create_tenant_store_user(db_session, suffix="exp-a", role="ADMIN")
    _tenant_b, store_b, user_b = _create_tenant_store_user(db_session, suffix="exp-b", role="ADMIN")

    token_a = login(client, user_a.username, "Pass1234!")
    token_b = login(client, user_b.username, "Pass1234!")
    today = date.today().isoformat()
    payload = {
        "source_type": "reports_daily",
        "format": "csv",
        "filters": {"store_id": str(store_a.id), "from": today, "to": today, "timezone": "UTC"},
        "transaction_id": "txn-cross-1",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "cross-exports"},
        json=payload,
    )
    assert response.status_code == 201
    export_id = response.json()["export_id"]

    other_detail = client.get(
        f"/aris3/exports/{export_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_detail.status_code == 422

    other_download = client.get(
        f"/aris3/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_download.status_code == 422


def test_exports_rbac_denied(client, db_session):
    seed_defaults(db_session)
    _tenant, store, user = _create_tenant_store_user(db_session, suffix="exp-user", role="USER")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()
    payload = {
        "source_type": "reports_daily",
        "format": "csv",
        "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
        "transaction_id": "txn-denied-1",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "denied-exports"},
        json=payload,
    )
    assert response.status_code == 403

    list_response = client.get("/aris3/exports", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 403
