from datetime import date, timedelta

from app.aris3.core.config import settings
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_reports_date_range_limit_validation(client, db_session, monkeypatch):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-day5-limits")
    token = login(client, user.username, "Pass1234!")

    monkeypatch.setattr(settings, "REPORTS_MAX_DATE_RANGE_DAYS", 1)

    start = date.today()
    end = start + timedelta(days=2)
    response = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": start.isoformat(), "to": end.isoformat(), "timezone": "UTC"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["details"]["reason_code"] == "REPORT_DATE_RANGE_LIMIT_EXCEEDED"


def test_exports_list_page_size_limit_validation(client, db_session, monkeypatch):
    seed_defaults(db_session)
    _tenant, _store, _other_store, user = create_tenant_user(db_session, suffix="exports-list-limits")
    token = login(client, user.username, "Pass1234!")

    monkeypatch.setattr(settings, "EXPORTS_LIST_MAX_PAGE_SIZE", 1)

    response = client.get(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 5},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["details"]["reason_code"] == "EXPORTS_PAGE_SIZE_LIMIT_EXCEEDED"
