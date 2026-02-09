from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_cash_session_open_success_and_duplicate_denied(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cash-open")
    token = login(client, user.username, "Pass1234!")

    payload = {
        "transaction_id": "txn-open-1",
        "store_id": str(store.id),
        "action": "OPEN",
        "opening_amount": 100.0,
        "business_date": date.today().isoformat(),
        "timezone": "UTC",
    }
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-open-1"}
    response = client.post("/aris3/pos/cash/session/actions", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"

    duplicate = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-open-2"},
        json={**payload, "transaction_id": "txn-open-2"},
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
