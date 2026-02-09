from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_security_boundaries_for_reconciliation_reads(client, db_session):
    seed_defaults(db_session)
    tenant_a, store_a, _other_store_a, manager_a = create_tenant_user(
        db_session, suffix="pos-cash-sec-a", role="MANAGER"
    )
    tenant_b, store_b, _other_store_b, _manager_b = create_tenant_user(
        db_session, suffix="pos-cash-sec-b", role="MANAGER"
    )
    token_a = login(client, manager_a.username, "Pass1234!")

    response = client.get(
        "/aris3/pos/cash/reconciliation/breakdown",
        headers={"Authorization": f"Bearer {token_a}"},
        params={
            "store_id": str(store_b.id),
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
            "tenant_id": str(tenant_b.id),
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] in {
        ErrorCatalog.CROSS_TENANT_ACCESS_DENIED.code,
        ErrorCatalog.STORE_SCOPE_MISMATCH.code,
    }


def test_rbac_denies_cash_read_access(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(
        db_session, suffix="pos-cash-sec-user", role="USER"
    )
    token = login(client, user.username, "Pass1234!")

    response = client.get(
        "/aris3/pos/cash/day-close/summary",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from_date": date.today().isoformat(), "to_date": date.today().isoformat()},
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code
