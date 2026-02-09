from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_reports_security_boundaries(client, db_session):
    seed_defaults(db_session)
    tenant_a, store_a, _store_a2, user_a = create_tenant_user(db_session, suffix="reports-sec-a")
    tenant_b, store_b, _store_b2, _user_b = create_tenant_user(db_session, suffix="reports-sec-b")
    token_a = login(client, user_a.username, "Pass1234!")

    today = date.today().isoformat()
    cross_tenant = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token_a}"},
        params={"store_id": str(store_b.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert cross_tenant.status_code == 403
    assert cross_tenant.json()["code"] in {
        ErrorCatalog.CROSS_TENANT_ACCESS_DENIED.code,
        ErrorCatalog.STORE_SCOPE_MISMATCH.code,
    }

    _tenant_c, store_c, _store_c2, user_c = create_tenant_user(db_session, suffix="reports-sec-c", role="USER")
    token_c = login(client, user_c.username, "Pass1234!")
    denied = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token_c}"},
        params={"store_id": str(store_c.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code
