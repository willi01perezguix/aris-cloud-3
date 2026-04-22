from datetime import date
from decimal import Decimal
from uuid import UUID

from app.aris3.db.models import PosSale
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def _overview(client, token: str, store_id: str, timezone: str = "UTC"):
    today = date.today().isoformat()
    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": store_id, "from": today, "to": today, "timezone": timezone},
    )
    assert response.status_code == 200
    return response.json()["totals"]


def test_reports_profit_single_line_real_profit(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other, user = create_tenant_user(db_session, suffix="reports-profit-single")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-429", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=429.0, cost_price=101.84)
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=429.0, sku="SKU-429", epc=None)],
        payments=[{"method": "CASH", "amount": 429.0}],
        create_txn="txn-profit-single-create",
        checkout_txn="txn-profit-single-checkout",
        idempotency_key="profit-single-create",
        checkout_idempotency_key="profit-single-checkout",
    )

    totals = _overview(client, token, str(store.id))
    assert Decimal(totals["gross_sales"]) == Decimal("429.00")
    assert Decimal(totals["net_cogs"]) == Decimal("101.84")
    assert Decimal(totals["net_profit"]) == Decimal("327.16")


def test_reports_profit_quantity_and_multi_line(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other, user = create_tenant_user(db_session, suffix="reports-profit-multi")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-QTY", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=429.0, cost_price=101.84)
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-QTY", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=429.0, cost_price=101.84)
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-2", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=100.0, cost_price=60.0)
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    create_paid_sale(
        client,
        token,
        str(store.id),
        [
            sale_line(line_type="SKU", qty=2, unit_price=429.0, sku="SKU-QTY", epc=None),
            sale_line(line_type="SKU", qty=1, unit_price=100.0, sku="SKU-2", epc=None),
        ],
        payments=[{"method": "CASH", "amount": 958.0}],
        create_txn="txn-profit-multi-create",
        checkout_txn="txn-profit-multi-checkout",
        idempotency_key="profit-multi-create",
        checkout_idempotency_key="profit-multi-checkout",
    )

    totals = _overview(client, token, str(store.id))
    assert Decimal(totals["gross_sales"]) == Decimal("958.00")
    assert Decimal(totals["net_cogs"]) == Decimal("263.68")
    assert Decimal(totals["net_profit"]) == Decimal("694.32")


def test_reports_lowercase_completed_store_isolation_and_draft_excluded(client, db_session):
    seed_defaults(db_session)
    tenant, store_a, store_b, user = create_tenant_user(db_session, suffix="reports-profit-store")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-A", store_id=str(store_a.id), epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=50.0, cost_price=20.0)
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-B", store_id=str(store_b.id), epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=80.0, cost_price=10.0)
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store_a.id), cashier_user_id=str(user.id))
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store_b.id), cashier_user_id=str(user.id))

    sale_a = create_paid_sale(
        client,
        token,
        str(store_a.id),
        [sale_line(line_type="SKU", qty=1, unit_price=50.0, sku="SKU-A", epc=None)],
        payments=[{"method": "CASH", "amount": 50.0}],
        create_txn="txn-profit-store-a-create",
        checkout_txn="txn-profit-store-a-checkout",
        idempotency_key="profit-store-a-create",
        checkout_idempotency_key="profit-store-a-checkout",
    )
    db_session.query(PosSale).filter(PosSale.id == UUID(sale_a["header"]["id"])).update({"status": "completed"})
    db_session.commit()

    create_paid_sale(
        client,
        token,
        str(store_b.id),
        [sale_line(line_type="SKU", qty=1, unit_price=80.0, sku="SKU-B", epc=None)],
        payments=[{"method": "CASH", "amount": 80.0}],
        create_txn="txn-profit-store-b-create",
        checkout_txn="txn-profit-store-b-checkout",
        idempotency_key="profit-store-b-create",
        checkout_idempotency_key="profit-store-b-checkout",
    )

    draft = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "profit-store-draft"},
        json=sale_payload(str(store_a.id), [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-A", epc=None)], transaction_id="txn-profit-store-draft"),
    )
    assert draft.status_code == 201

    db_session.commit()

    totals_a = _overview(client, token, str(store_a.id))
    assert Decimal(totals_a["gross_sales"]) == Decimal("50.00")
    assert Decimal(totals_a["net_profit"]) == Decimal("30.00")


def test_reports_missing_cost_and_line_level_return_reversal(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other, user = create_tenant_user(db_session, suffix="reports-profit-refund")
    token = login(client, user.username, "Pass1234!")

    # One line with missing deterministic cost fallback (no stock row), one line with known cost and qty=2.
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-RET", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=429.0, cost_price=101.84)
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-RET", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=429.0, cost_price=101.84)
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-NO-COST", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=50.0, cost_price=None)
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [
            sale_line(line_type="SKU", qty=2, unit_price=429.0, sku="SKU-RET", epc=None),
            sale_line(line_type="SKU", qty=1, unit_price=50.0, sku="SKU-NO-COST", epc=None),
        ],
        payments=[{"method": "CASH", "amount": 908.0}],
        create_txn="txn-profit-refund-create",
        checkout_txn="txn-profit-refund-checkout",
        idempotency_key="profit-refund-create",
        checkout_idempotency_key="profit-refund-checkout",
    )

    line_id = sale["lines"][0]["id"]
    refund = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "profit-refund-action"},
        json={
            "transaction_id": "txn-profit-refund-action",
            "action": "REFUND_ITEMS",
            "receipt_number": "RCPT-PROFIT-RET",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CASH", "amount": 429.0}],
        },
    )
    assert refund.status_code == 200

    totals = _overview(client, token, str(store.id), timezone="America/Guatemala")
    assert Decimal(totals["gross_sales"]) == Decimal("908.00")
    assert Decimal(totals["refunds_total"]) == Decimal("429.00")
    assert Decimal(totals["net_sales"]) == Decimal("479.00")
    assert Decimal(totals["cogs_gross"]) == Decimal("203.68")
    assert Decimal(totals["cogs_reversed_from_returns"]) == Decimal("101.84")
    assert Decimal(totals["net_cogs"]) == Decimal("101.84")
    assert Decimal(totals["net_profit"]) == Decimal("377.16")
