from datetime import date
from decimal import Decimal

from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    seed_defaults,
)


def _overview(client, token: str, store_id: str, *, payment_method: str | None = None):
    today = date.today().isoformat()
    params = {"store_id": store_id, "from": today, "to": today, "timezone": "UTC"}
    if payment_method:
        params["payment_method"] = payment_method
    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    assert response.status_code == 200
    return response.json()["totals"]


def _create_draft_return(client, token: str, store_id: str, sale_id: str, sale_line_id: str, key: str) -> str:
    payload = {
        "transaction_id": f"txn-{key}",
        "store_id": store_id,
        "sale_id": sale_id,
        "items": [
            {
                "sale_line_id": sale_line_id,
                "qty": 1,
                "condition": "NEW",
                "resolution": "REFUND",
            }
        ],
    }
    response = client.post(
        "/aris3/pos/returns",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_reports_ignore_draft_and_voided_returns_from_canonical_flow(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-returns-state")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-RSTATE",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))
    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=20.0, sku="SKU-RSTATE", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 20.0}],
        create_txn="txn-rstate-sale",
        checkout_txn="txn-rstate-checkout",
        idempotency_key="rstate-sale",
        checkout_idempotency_key="rstate-checkout",
    )

    draft_id = _create_draft_return(
        client,
        token,
        str(store.id),
        sale["header"]["id"],
        sale["lines"][0]["id"],
        "rstate-draft",
    )
    totals_after_draft = _overview(client, token, str(store.id))
    assert Decimal(totals_after_draft["refunds_total"]) == Decimal("0.00")

    void_response = client.post(
        f"/aris3/pos/returns/{draft_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "rstate-void"},
        json={"transaction_id": "txn-rstate-void", "action": "VOID", "reason": "operator_cancel"},
    )
    assert void_response.status_code == 200
    totals_after_void = _overview(client, token, str(store.id))
    assert Decimal(totals_after_void["refunds_total"]) == Decimal("0.00")

    complete_id = _create_draft_return(
        client,
        token,
        str(store.id),
        sale["header"]["id"],
        sale["lines"][0]["id"],
        "rstate-complete",
    )
    complete_response = client.post(
        f"/aris3/pos/returns/{complete_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "rstate-complete-action"},
        json={
            "transaction_id": "txn-rstate-complete-action",
            "action": "COMPLETE",
            "settlement_payments": [{"method": "CASH", "amount": 20.0}],
        },
    )
    assert complete_response.status_code == 200
    totals_after_complete = _overview(client, token, str(store.id))
    assert Decimal(totals_after_complete["refunds_total"]) == Decimal("20.00")


def test_reports_payment_method_filter_applies_to_refunds_and_sales(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-payment-filter")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CASH",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CARD",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    cash_sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-CASH", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 10.0}],
        create_txn="txn-cash-sale",
        checkout_txn="txn-cash-checkout",
        idempotency_key="cash-sale",
        checkout_idempotency_key="cash-checkout",
    )
    create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=15.0, sku="SKU-CARD", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 15.0, "authorization_code": "AUTH-RPT"}],
        create_txn="txn-card-sale",
        checkout_txn="txn-card-checkout",
        idempotency_key="card-sale",
        checkout_idempotency_key="card-checkout",
    )

    draft_id = _create_draft_return(
        client,
        token,
        str(store.id),
        cash_sale["header"]["id"],
        cash_sale["lines"][0]["id"],
        "payment-filter-return",
    )
    complete_response = client.post(
        f"/aris3/pos/returns/{draft_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "payment-filter-complete"},
        json={
            "transaction_id": "txn-payment-filter-complete",
            "action": "COMPLETE",
            "settlement_payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert complete_response.status_code == 200

    card_totals = _overview(client, token, str(store.id), payment_method="CARD")
    assert Decimal(card_totals["gross_sales"]) == Decimal("15.00")
    assert Decimal(card_totals["refunds_total"]) == Decimal("0.00")
    assert Decimal(card_totals["net_sales"]) == Decimal("15.00")
    assert card_totals["orders_paid_count"] == 1

    cash_totals = _overview(client, token, str(store.id), payment_method="CASH")
    assert Decimal(cash_totals["gross_sales"]) == Decimal("10.00")
    assert Decimal(cash_totals["refunds_total"]) == Decimal("10.00")
    assert Decimal(cash_totals["net_sales"]) == Decimal("0.00")
    assert cash_totals["orders_paid_count"] == 1
