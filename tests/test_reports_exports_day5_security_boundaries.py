import uuid
from datetime import date

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import User
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_reports_exports_cross_tenant_and_store_scope_denied(client, db_session):
    seed_defaults(db_session)
    tenant_a, store_a, other_store_a, user_a = create_tenant_user(db_session, suffix="reports-sec-a")
    _tenant_b, store_b, _other_store_b, _user_b = create_tenant_user(db_session, suffix="reports-sec-b")
    token_a = login(client, user_a.username, "Pass1234!")

    today = date.today().isoformat()
    report_response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token_a}"},
        params={"store_id": str(store_b.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert report_response.status_code == 403
    assert report_response.json()["code"] == "STORE_SCOPE_MISMATCH"

    export_response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "cross-tenant-export"},
        json={
            "source_type": "reports_daily",
            "format": "csv",
            "filters": {"store_id": str(store_b.id), "from": today, "to": today, "timezone": "UTC"},
            "transaction_id": "txn-cross-tenant",
        },
    )
    assert export_response.status_code == 403
    assert export_response.json()["code"] == "STORE_SCOPE_MISMATCH"

    manager = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        store_id=store_a.id,
        username="manager-reports-sec",
        email="manager-reports-sec@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="MANAGER",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(manager)
    db_session.commit()

    manager_token = login(client, manager.username, "Pass1234!")
    store_scope_response = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {manager_token}"},
        params={"store_id": str(other_store_a.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert store_scope_response.status_code == 403
    assert store_scope_response.json()["code"] == "STORE_SCOPE_MISMATCH"


def test_reports_rbac_denied_without_permission(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-sec-user", role="USER")
    token = login(client, user.username, "Pass1234!")

    today = date.today().isoformat()
    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
