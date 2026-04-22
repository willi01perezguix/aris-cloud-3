from datetime import date
from decimal import Decimal

import pytest

from app.aris3.services.exports import build_report_dataset
from app.aris3.services.reports import build_report_totals
from app.aris3.schemas.exports import ExportFilters


def test_build_report_totals_defaults_missing_liability_fields_to_zero():
    rows = [
        {
            "business_date": date(2026, 4, 1),
            "gross_sales": Decimal("100.00"),
            "refunds_total": Decimal("10.00"),
            "net_sales": Decimal("90.00"),
            "cogs_gross": Decimal("20.00"),
            "cogs_reversed_from_returns": Decimal("0.00"),
            "net_cogs": Decimal("20.00"),
            "net_profit": Decimal("70.00"),
            "orders_paid_count": 2,
            "average_ticket": Decimal("45.00"),
        }
    ]

    totals = build_report_totals(rows)

    assert totals["liability_issued_advances"] == Decimal("0.00")
    assert totals["liability_issued_gift_cards"] == Decimal("0.00")
    assert totals["liability_redeemed_advances"] == Decimal("0.00")
    assert totals["liability_redeemed_gift_cards"] == Decimal("0.00")
    assert totals["liability_refunded_advances"] == Decimal("0.00")
    assert totals["liability_refunded_gift_cards"] == Decimal("0.00")
    assert totals["tender_cash_received"] == Decimal("0.00")
    assert totals["tender_card_received"] == Decimal("0.00")
    assert totals["tender_transfer_received"] == Decimal("0.00")
    assert totals["tender_total_received"] == Decimal("0.00")


def test_build_report_dataset_reports_overview_handles_rows_without_liability_keys(monkeypatch):
    monkeypatch.setattr(
        "app.aris3.services.exports.daily_sales_refunds",
        lambda *args, **kwargs: (
            {date(2026, 4, 1): Decimal("100.00")},
            {date(2026, 4, 1): 1},
            {date(2026, 4, 1): Decimal("0.00")},
            {date(2026, 4, 1): Decimal("0.00")},
            {date(2026, 4, 1): Decimal("0.00")},
            {"missing_cost_lines": 0, "missing_cost_total_qty": 0, "cost_source_summary": {}},
        ),
    )

    monkeypatch.setattr(
        "app.aris3.services.exports.build_daily_report_rows",
        lambda *args, **kwargs: [
            {
                "business_date": date(2026, 4, 1),
                "gross_sales": Decimal("100.00"),
                "refunds_total": Decimal("0.00"),
                "net_sales": Decimal("100.00"),
                "cogs_gross": Decimal("0.00"),
                "cogs_reversed_from_returns": Decimal("0.00"),
                "net_cogs": Decimal("0.00"),
                "net_profit": Decimal("100.00"),
                "orders_paid_count": 1,
                "average_ticket": Decimal("100.00"),
            }
        ],
    )

    dataset = build_report_dataset(
        db=None,
        tenant_id="tenant",
        store_id="store",
        source_type="reports_overview",
        filters=ExportFilters(store_id="store", **{"from": "2026-04-01", "to": "2026-04-01"}, timezone="UTC"),
        max_days=31,
    )

    assert dataset.totals is not None
    assert dataset.totals["liability_issued_advances"] == Decimal("0.00")
    assert dataset.totals["tender_total_received"] == Decimal("0.00")


@pytest.mark.parametrize(
    "missing_field",
    [
        "liability_issued_advances",
        "liability_issued_gift_cards",
        "liability_redeemed_advances",
        "liability_redeemed_gift_cards",
        "liability_refunded_advances",
        "liability_refunded_gift_cards",
        "tender_cash_received",
        "tender_card_received",
        "tender_transfer_received",
        "tender_total_received",
    ],
)
def test_build_report_totals_missing_field_does_not_raise_or_change_totals(missing_field):
    row = {
        "business_date": date(2026, 4, 1),
        "gross_sales": Decimal("100.00"),
        "refunds_total": Decimal("10.00"),
        "net_sales": Decimal("90.00"),
        "cogs_gross": Decimal("20.00"),
        "cogs_reversed_from_returns": Decimal("0.00"),
        "net_cogs": Decimal("20.00"),
        "net_profit": Decimal("70.00"),
        "orders_paid_count": 2,
        "average_ticket": Decimal("45.00"),
        "liability_issued_advances": Decimal("1.00"),
        "liability_issued_gift_cards": Decimal("2.00"),
        "liability_redeemed_advances": Decimal("3.00"),
        "liability_redeemed_gift_cards": Decimal("4.00"),
        "liability_refunded_advances": Decimal("5.00"),
        "liability_refunded_gift_cards": Decimal("6.00"),
        "tender_cash_received": Decimal("7.00"),
        "tender_card_received": Decimal("8.00"),
        "tender_transfer_received": Decimal("9.00"),
        "tender_total_received": Decimal("24.00"),
    }
    row.pop(missing_field)

    totals = build_report_totals([row])

    expected_defaults = {
        "liability_issued_advances": Decimal("1.00"),
        "liability_issued_gift_cards": Decimal("2.00"),
        "liability_redeemed_advances": Decimal("3.00"),
        "liability_redeemed_gift_cards": Decimal("4.00"),
        "liability_refunded_advances": Decimal("5.00"),
        "liability_refunded_gift_cards": Decimal("6.00"),
        "tender_cash_received": Decimal("7.00"),
        "tender_card_received": Decimal("8.00"),
        "tender_transfer_received": Decimal("9.00"),
        "tender_total_received": Decimal("24.00"),
    }
    expected_defaults[missing_field] = Decimal("0.00")
    expected_defaults["tender_total_received"] = (
        expected_defaults["tender_cash_received"]
        + expected_defaults["tender_card_received"]
        + expected_defaults["tender_transfer_received"]
    )

    for key, expected in expected_defaults.items():
        assert totals[key] == expected
