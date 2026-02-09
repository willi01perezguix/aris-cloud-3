from datetime import date
from decimal import Decimal
import csv
import io

from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    seed_defaults,
)


def _create_export(client, token: str, store_id: str, *, source_type: str, key: str):
    today = date.today().isoformat()
    payload = {
        "source_type": source_type,
        "format": "csv",
        "filters": {"store_id": store_id, "from": today, "to": today, "timezone": "UTC"},
        "transaction_id": f"txn-{key}",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def _download_csv(client, token: str, export_id: str) -> list[dict]:
    response = client.get(
        f"/aris3/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    reader = csv.DictReader(io.StringIO(response.content.decode("utf-8")))
    return list(reader)


def test_exports_parity_with_reports(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-parity")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))
    create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=12.0, sku="SKU-1", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 12.0}],
        create_txn="txn-parity-sale",
        checkout_txn="txn-parity-checkout",
        idempotency_key="parity-sale",
        checkout_idempotency_key="parity-checkout",
    )

    today = date.today().isoformat()
    reports_daily = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert reports_daily.status_code == 200
    daily_row = reports_daily.json()["rows"][0]

    export_daily = _create_export(client, token, str(store.id), source_type="reports_daily", key="parity-daily")
    daily_rows = _download_csv(client, token, export_daily["export_id"])
    assert len(daily_rows) == 1
    exported_daily = daily_rows[0]
    assert exported_daily["business_date"] == daily_row["business_date"]
    assert Decimal(exported_daily["gross_sales"]) == Decimal(daily_row["gross_sales"])
    assert Decimal(exported_daily["net_sales"]) == Decimal(daily_row["net_sales"])
    assert int(exported_daily["orders_paid_count"]) == daily_row["orders_paid_count"]

    reports_overview = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert reports_overview.status_code == 200
    overview_totals = reports_overview.json()["totals"]

    export_overview = _create_export(client, token, str(store.id), source_type="reports_overview", key="parity-overview")
    overview_rows = _download_csv(client, token, export_overview["export_id"])
    assert len(overview_rows) == 1
    exported_overview = overview_rows[0]
    assert Decimal(exported_overview["gross_sales"]) == Decimal(overview_totals["gross_sales"])
    assert Decimal(exported_overview["net_sales"]) == Decimal(overview_totals["net_sales"])
