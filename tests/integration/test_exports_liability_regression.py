from datetime import date
from decimal import Decimal

from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_exports_create_handles_legacy_daily_rows_without_liability_fields(client, db_session, monkeypatch):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-liability-regression")
    token = login(client, user.username, "Pass1234!")

    monkeypatch.setattr(
        "app.aris3.services.exports.daily_sales_refunds",
        lambda *args, **kwargs: ({date(2026, 4, 1): Decimal("10.00")}, {date(2026, 4, 1): 1}, {date(2026, 4, 1): Decimal("0.00")}),
    )
    monkeypatch.setattr(
        "app.aris3.services.exports.build_daily_report_rows",
        lambda *args, **kwargs: [
            {
                "business_date": date(2026, 4, 1),
                "gross_sales": Decimal("10.00"),
                "refunds_total": Decimal("0.00"),
                "net_sales": Decimal("10.00"),
                "cogs_gross": Decimal("0.00"),
                "cogs_reversed_from_returns": Decimal("0.00"),
                "net_cogs": Decimal("0.00"),
                "net_profit": Decimal("10.00"),
                "orders_paid_count": 1,
                "average_ticket": Decimal("10.00"),
            }
        ],
    )

    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exports-liability-regression"},
        json={
            "transaction_id": "txn-exports-liability-regression",
            "source_type": "reports_overview",
            "format": "csv",
            "filters": {
                "store_id": str(store.id),
                "from": "2026-04-01",
                "to": "2026-04-01",
                "timezone": "UTC",
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "READY"
