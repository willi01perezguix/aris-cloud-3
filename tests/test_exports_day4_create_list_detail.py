from datetime import date

import pytest

from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def _create_export(client, token: str, store_id: str, *, source_type: str, export_format: str, key: str):
    today = date.today().isoformat()
    payload = {
        "source_type": source_type,
        "format": export_format,
        "filters": {"store_id": store_id, "from": today, "to": today, "timezone": "UTC"},
        "file_name": f"report-{source_type}",
        "transaction_id": f"txn-{key}",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize("source_type", ["reports_overview", "reports_daily", "reports_calendar"])
@pytest.mark.parametrize("export_format", ["csv", "xlsx", "pdf"])
def test_exports_create_list_detail(client, db_session, source_type, export_format):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix=f"exports-{source_type}-{export_format}")
    token = login(client, user.username, "Pass1234!")

    created = _create_export(
        client,
        token,
        str(store.id),
        source_type=source_type,
        export_format=export_format,
        key=f"exp-{source_type}-{export_format}",
    )
    assert created["status"] == "READY"
    assert created["format"] == export_format
    assert created["source_type"] == source_type
    assert created["file_name"].endswith(f".{export_format}")

    list_response = client.get("/aris3/exports", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    rows = list_response.json()["rows"]
    assert any(row["export_id"] == created["export_id"] for row in rows)

    detail_response = client.get(
        f"/aris3/exports/{created['export_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["export_id"] == created["export_id"]
