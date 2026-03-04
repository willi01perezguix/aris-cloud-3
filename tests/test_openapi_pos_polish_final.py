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
    assert returns_actions["discriminator"]["propertyName"] == "action"
    assert cash_actions["discriminator"]["propertyName"] == "action"


def test_pos_patch_sale_documents_draft_only_full_line_replacement():
    operation = app.openapi()["paths"]["/aris3/pos/sales/{sale_id}"]["patch"]
    description = operation.get("description") or ""

    assert "DRAFT" in description
    assert "full replacement" in description


def test_pos_tenant_id_and_legacy_fields_are_deprecated_in_contract():
    schemas = app.openapi()["components"]["schemas"]

    assert schemas["PosSaleCreateRequest"]["properties"]["tenant_id"]["deprecated"] is True
    assert schemas["PosSaleUpdateRequest"]["properties"]["tenant_id"]["deprecated"] is True
    assert schemas["ReturnQuoteRequest"]["properties"]["tenant_id"]["deprecated"] is True
    assert schemas["OpenCashSessionRequest"]["properties"]["tenant_id"]["deprecated"] is True

    sku_line = schemas["SaleLineBySkuInput"]["properties"]
    assert sku_line["unit_price"]["deprecated"] is True
    assert sku_line["status"]["deprecated"] is True
    assert sku_line["location_code"]["deprecated"] is True
    assert sku_line["pool"]["deprecated"] is True
    assert sku_line["snapshot"]["deprecated"] is True
