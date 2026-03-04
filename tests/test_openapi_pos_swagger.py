from app.main import app


POS_SALES_ENDPOINTS = [
    ("/aris3/pos/sales", "get"),
    ("/aris3/pos/sales", "post"),
    ("/aris3/pos/sales/{sale_id}", "patch"),
    ("/aris3/pos/sales/{sale_id}", "get"),
    ("/aris3/pos/sales/{sale_id}/actions", "post"),
]

POS_CASH_ENDPOINTS = [
    ("/aris3/pos/cash/session/current", "get"),
    ("/aris3/pos/cash/session/actions", "post"),
    ("/aris3/pos/cash/movements", "get"),
    ("/aris3/pos/cash/day-close/actions", "post"),
    ("/aris3/pos/cash/day-close/summary", "get"),
    ("/aris3/pos/cash/reconciliation/breakdown", "get"),
]

ERROR_CODES = {"401", "403", "404", "409", "422"}
MONEY_EXAMPLES = {"0.00", "25.00", "125.50", "-10.00"}


def test_pos_endpoints_document_standard_error_responses():
    paths = app.openapi()["paths"]
    for path, method in POS_SALES_ENDPOINTS + POS_CASH_ENDPOINTS:
        responses = paths[path][method]["responses"]
        assert ERROR_CODES.issubset(responses.keys())


def test_pos_action_enums_are_visible_in_openapi():
    components = app.openapi()["components"]["schemas"]
    sale_action = components["PosSaleActionRequest"]["properties"]["action"]
    assert sale_action["enum"] == ["checkout", "cancel", "REFUND_ITEMS", "EXCHANGE_ITEMS"]

    cash_action = components["PosCashSessionActionRequest"]["properties"]["action"]
    assert cash_action["enum"] == ["OPEN", "CASH_IN", "CASH_OUT", "CLOSE"]


def test_pos_monetary_fields_use_readable_examples():
    components = app.openapi()["components"]["schemas"]
    checked_fields = {
        "PosSaleHeaderResponse": ["total_due", "paid_total", "balance_due", "change_due"],
        "PosSaleLineResponse": ["unit_price", "line_total"],
        "PosPaymentResponse": ["amount"],
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

    for schema_name, fields in checked_fields.items():
        schema = components[schema_name]
        for field in fields:
            examples = set(schema["properties"][field].get("examples", []))
            assert examples
            assert examples.issubset(MONEY_EXAMPLES)


def test_pos_cash_tenant_id_filters_are_deprecated_for_compatibility():
    paths = app.openapi()["paths"]
    for path in [
        "/aris3/pos/cash/session/current",
        "/aris3/pos/cash/movements",
        "/aris3/pos/cash/day-close/summary",
        "/aris3/pos/cash/reconciliation/breakdown",
    ]:
        params = {param["name"]: param for param in paths[path]["get"].get("parameters", [])}
        tenant_param = params["tenant_id"]
        assert tenant_param["deprecated"] is True
        assert "resolved from JWT/context" in tenant_param.get("description", "")


def test_current_session_contract_is_200_with_nullable_session_payload():
    op = app.openapi()["paths"]["/aris3/pos/cash/session/current"]["get"]
    success_schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert success_schema["$ref"] == "#/components/schemas/PosCashSessionCurrentResponse"

    current_schema = app.openapi()["components"]["schemas"]["PosCashSessionCurrentResponse"]
    assert "session" in current_schema["properties"]
    assert any(item.get("type") == "null" for item in current_schema["properties"]["session"]["anyOf"])


def test_pos_sales_list_filters_and_receipt_are_documented():
    paths = app.openapi()["paths"]
    params = {param["name"]: param for param in paths["/aris3/pos/sales"]["get"].get("parameters", [])}
    for name in ["receipt_number", "status", "from_date", "to_date", "q", "page", "page_size", "sku", "epc"]:
        assert name in params

    components = app.openapi()["components"]["schemas"]
    header = components["PosSaleHeaderResponse"]["properties"]
    assert "receipt_number" in header


def test_pos_returns_examples_are_present_in_openapi():
    op = app.openapi()["paths"]["/aris3/pos/sales/{sale_id}/actions"]["post"]
    examples = op["requestBody"]["content"]["application/json"]["examples"]
    assert {"refund_only", "exchange_only", "refund_and_exchange"}.issubset(set(examples.keys()))
