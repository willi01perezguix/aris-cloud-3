from app.main import app


POS_ENDPOINTS_WITH_404 = [
    ("/aris3/pos/sales", "post"),
    ("/aris3/pos/sales/{sale_id}", "patch"),
    ("/aris3/pos/sales/{sale_id}", "get"),
    ("/aris3/pos/sales/{sale_id}/actions", "post"),
    ("/aris3/pos/cash/session/current", "get"),
    ("/aris3/pos/cash/session/actions", "post"),
    ("/aris3/pos/cash/day-close/actions", "post"),
    ("/aris3/pos/cash/reconciliation/breakdown", "get"),
]
POS_LIST_ENDPOINTS_WITHOUT_404 = [
    ("/aris3/pos/sales", "get"),
    ("/aris3/pos/cash/movements", "get"),
    ("/aris3/pos/cash/day-close/summary", "get"),
]


def test_pos_endpoints_document_error_responses_consistently():
    paths = app.openapi()["paths"]
    for path, method in POS_ENDPOINTS_WITH_404:
        responses = paths[path][method]["responses"]
        assert {"401", "403", "404", "409", "422"}.issubset(responses.keys())

    for path, method in POS_LIST_ENDPOINTS_WITHOUT_404:
        responses = paths[path][method]["responses"]
        assert {"401", "403", "409", "422"}.issubset(responses.keys())
        assert "404" not in responses


def test_pos_action_request_uses_discriminator_oneof():
    schema = app.openapi()["paths"]["/aris3/pos/sales/{sale_id}/actions"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert "oneOf" in schema
    assert schema["discriminator"]["propertyName"] == "action"


def test_pos_sales_list_filters_and_shape_are_documented():
    op = app.openapi()["paths"]["/aris3/pos/sales"]["get"]
    params = {param["name"]: param for param in op.get("parameters", [])}
    for name in ["receipt_number", "status", "checked_out_from", "checked_out_to", "q", "page", "page_size", "sku", "epc"]:
        assert name in params

    components = app.openapi()["components"]["schemas"]
    assert components["SaleListResponse"]["required"] == ["page", "page_size", "total", "rows"]
    summary_row = components["SaleSummaryRow"]["properties"]
    for field in ["id", "receipt_number", "store_id", "status", "total_due", "paid_total", "balance_due", "item_count", "payment_summary"]:
        assert field in summary_row


def test_sales_actions_primary_examples_are_checkout_cancel():
    op = app.openapi()["paths"]["/aris3/pos/sales/{sale_id}/actions"]["post"]
    examples = op["requestBody"]["content"]["application/json"]["examples"]
    assert {"checkout", "cancel"}.issubset(set(examples.keys()))



def test_pos_sales_list_get_has_no_request_body():
    op = app.openapi()["paths"]["/aris3/pos/sales"]["get"]
    assert "requestBody" not in op


def test_pos_sales_patch_uses_update_schema():
    op = app.openapi()["paths"]["/aris3/pos/sales/{sale_id}"]["patch"]
    schema = op["requestBody"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/PosSaleUpdateRequest")
