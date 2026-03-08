from app.main import app


def test_pos_line_inputs_are_discriminated_for_sales_and_returns():
    schemas = app.openapi()["components"]["schemas"]

    create_lines = schemas["PosSaleCreateRequest"]["properties"]["lines"]["items"]
    assert create_lines["discriminator"]["propertyName"] == "line_type"
    assert {"SaleLineBySkuInput", "SaleLineByEpcInput"} == {
        ref["$ref"].split("/")[-1] for ref in create_lines["oneOf"]
    }

    exchange_lines = schemas["ReturnQuoteRequest"]["properties"]["exchange_lines"]["anyOf"][0]["items"]
    assert exchange_lines["discriminator"]["propertyName"] == "line_type"


def test_pos_action_endpoints_expose_discriminators_in_openapi():
    paths = app.openapi()["paths"]

    sales_actions = paths["/aris3/pos/sales/{sale_id}/actions"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    returns_actions = paths["/aris3/pos/returns/{return_id}/actions"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    cash_actions = paths["/aris3/pos/cash/session/actions"]["post"]["requestBody"]["content"]["application/json"]["schema"]

    assert sales_actions["discriminator"]["propertyName"] == "action"
    assert sales_actions["discriminator"]["mapping"].keys() == {"CHECKOUT", "CANCEL"}
    assert returns_actions["discriminator"]["propertyName"] == "action"
    assert cash_actions["discriminator"]["propertyName"] == "action"


def test_pos_sale_line_required_contract_is_canonical():
    schemas = app.openapi()["components"]["schemas"]
    sku_required = set(schemas["SaleLineBySkuInput"].get("required", []))
    epc_required = set(schemas["SaleLineByEpcInput"].get("required", []))

    assert {"sku"}.issubset(sku_required)
    assert "epc" not in sku_required
    assert {"epc"}.issubset(epc_required)
    assert "sku" not in epc_required


def test_pos_patch_sale_documents_draft_only_full_line_replacement():
    operation = app.openapi()["paths"]["/aris3/pos/sales/{sale_id}"]["patch"]
    description = operation.get("description") or ""

    assert "DRAFT" in description
    assert "full replacement" in description
