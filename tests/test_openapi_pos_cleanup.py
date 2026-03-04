from app.main import app


MONEY_FIELDS = {
    "PosSaleHeaderResponse": ["total_due", "paid_total", "balance_due", "change_due"],
    "PosSaleLineResponse": ["unit_price", "line_total"],
    "PosPaymentResponse": ["amount"],
    "PosPaymentCreate": ["amount"],
    "PosCashSessionSummary": ["opening_amount", "expected_cash", "counted_cash", "difference"],
    "PosCashMovementResponse": ["amount", "expected_balance_before", "expected_balance_after"],
    "PosCashDayCloseResponse": [
        "expected_cash",
        "counted_cash",
        "difference_amount",
        "net_cash_sales",
        "cash_refunds",
        "net_cash_movement",
        "day_close_difference",
    ],
    "PosCashReconciliationBreakdownResponse": [
        "expected_cash",
        "opening_amount",
        "cash_in",
        "cash_out",
        "net_cash_movement",
        "net_cash_sales",
        "cash_refunds",
        "day_close_difference",
    ],
}


def test_pos_openapi_money_fields_use_decimal_string_examples():
    components = app.openapi()["components"]["schemas"]
    for component_name, field_names in MONEY_FIELDS.items():
        properties = components[component_name]["properties"]
        for field_name in field_names:
            schema = properties[field_name]
            sample = schema.get("examples", [None])[0]
            if sample is None and "anyOf" in schema:
                sample = next((item.get("examples", [None])[0] for item in schema["anyOf"] if item.get("examples")), None)
            assert sample in {"0.00", "25.00", "25.50", "50.00", "100.00", "125.00", "125.50", "24.50", "250.00"}


def test_pos_cash_get_endpoints_deprecate_tenant_id_query_param():
    paths = app.openapi()["paths"]
    for path in [
        "/aris3/pos/cash/session/current",
        "/aris3/pos/cash/movements",
        "/aris3/pos/cash/day-close/summary",
        "/aris3/pos/cash/reconciliation/breakdown",
    ]:
        tenant_param = next(p for p in paths[path]["get"]["parameters"] if p["name"] == "tenant_id")
        assert tenant_param["deprecated"] is True


def test_pos_current_session_contract_is_documented_as_200_with_nullable_session():
    op = app.openapi()["paths"]["/aris3/pos/cash/session/current"]["get"]
    schema_ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    session_schema = app.openapi()["components"]["schemas"][schema_ref.rsplit("/", 1)[-1]]
    assert session_schema["properties"]["session"]["anyOf"][1]["type"] == "null"


def test_pos_openapi_actions_show_allowed_enums():
    components = app.openapi()["components"]["schemas"]
    sale_action_enum = components["PosSaleActionRequest"]["properties"]["action"]["enum"]
    cash_action_enum = components["PosCashSessionActionRequest"]["properties"]["action"]["enum"]
    assert {"checkout", "cancel"}.issubset(set(sale_action_enum))
    assert {"OPEN", "CASH_IN", "CASH_OUT"}.issubset(set(cash_action_enum))


def test_pos_openapi_documents_standard_business_errors():
    paths = app.openapi()["paths"]
    op = paths["/aris3/pos/sales/{sale_id}/actions"]["post"]
    for status in ["401", "403", "404", "409"]:
        assert status in op["responses"]
        assert "$ref" in op["responses"][status]["content"]["application/json"]["schema"]

    conflict_examples = op["responses"]["409"]["content"]["application/json"]["examples"]
    assert "cash_checkout_requires_open_session" in conflict_examples
