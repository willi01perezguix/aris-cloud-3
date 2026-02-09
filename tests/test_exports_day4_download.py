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


@pytest.mark.parametrize(
    ("export_format", "content_type"),
    [
        ("csv", "text/csv"),
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("pdf", "application/pdf"),
    ],
)
def test_exports_download(client, db_session, export_format, content_type):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix=f"exports-download-{export_format}")
    token = login(client, user.username, "Pass1234!")

    created = _create_export(
        client,
        token,
        str(store.id),
        source_type="reports_daily",
        export_format=export_format,
        key=f"exp-download-{export_format}",
    )
    download = client.get(
        f"/aris3/exports/{created['export_id']}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(content_type)
    assert f".{export_format}" in download.headers["content-disposition"]
    assert download.content
