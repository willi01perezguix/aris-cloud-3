from datetime import datetime
from decimal import Decimal

from app.aris3.db.models import PosSale
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_reports_overview_falls_back_to_sale_total_when_lines_missing(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-fallback-sale-total")
    token = login(client, user.username, "Pass1234!")

    db_session.add(
        PosSale(
            tenant_id=tenant.id,
            store_id=store.id,
            status="PAID",
            total_due=42.5,
            paid_total=42.5,
            balance_due=0.0,
            change_due=0.0,
            checked_out_by_user_id=user.id,
            checked_out_at=datetime(2026, 4, 22, 5, 30, 0),
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            created_at=datetime(2026, 4, 21, 8, 10, 0),
            updated_at=datetime(2026, 4, 22, 5, 30, 0),
        )
    )
    db_session.commit()

    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "store_id": str(store.id),
            "from": "2026-04-21",
            "to": "2026-04-21",
            "timezone": "America/Guatemala",
        },
    )
    assert response.status_code == 200
    totals = response.json()["totals"]
    assert Decimal(totals["gross_sales"]) == Decimal("42.50")
    assert totals["orders_paid_count"] == 1
    assert Decimal(totals["average_ticket"]) == Decimal("42.50")


def test_reports_overview_counts_legacy_completed_status_for_same_local_day(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-fallback-legacy-status")
    token = login(client, user.username, "Pass1234!")

    db_session.add(
        PosSale(
            tenant_id=tenant.id,
            store_id=store.id,
            status="completed",
            total_due=30.0,
            paid_total=30.0,
            balance_due=0.0,
            change_due=0.0,
            checked_out_by_user_id=user.id,
            checked_out_at=datetime(2026, 4, 22, 5, 30, 0),
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            created_at=datetime(2026, 4, 21, 8, 10, 0),
            updated_at=datetime(2026, 4, 22, 5, 30, 0),
        )
    )
    db_session.commit()

    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "store_id": str(store.id),
            "from": "2026-04-21",
            "to": "2026-04-21",
            "timezone": "America/Guatemala",
        },
    )
    assert response.status_code == 200
    totals = response.json()["totals"]
    assert Decimal(totals["gross_sales"]) == Decimal("30.00")
    assert totals["orders_paid_count"] == 1
    assert Decimal(totals["average_ticket"]) == Decimal("30.00")
