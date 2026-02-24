from app.main import app


PRICE_FIELDS = {
    "cost_price": "25.00",
    "suggested_price": "35.00",
    "sale_price": "32.50",
}


def _assert_request_price_property(schema: dict, field: str, example: str):
    prop = schema["properties"][field]
    numeric = prop["anyOf"][0]
    assert numeric["type"] == "number"
    assert numeric["minimum"] == 0.0
    assert prop["examples"] == [example]


def _assert_response_price_property(schema: dict, field: str, example: str):
    prop = schema["properties"][field]
    serialized = prop["anyOf"][0]
    assert serialized["type"] == "string"
    assert serialized["pattern"] == r"^\d{1,10}(?:\.\d{2})?$"
    assert prop["examples"] == [example]


def test_stock_openapi_price_fields_have_constraints_and_examples_in_request_models():
    components = app.openapi()["components"]["schemas"]

    for component_name in ("StockDataBlock", "StockImportSkuLine", "StockImportEpcLine"):
        schema = components[component_name]
        for field, example in PRICE_FIELDS.items():
            _assert_request_price_property(schema, field, example)


def test_stock_openapi_price_fields_have_consistent_serialized_shape_in_response_model():
    stock_row = app.openapi()["components"]["schemas"]["StockRow"]
    for field, example in PRICE_FIELDS.items():
        _assert_response_price_property(stock_row, field, example)


def test_migrate_stock_request_uses_stock_data_block_price_constraints():
    components = app.openapi()["components"]["schemas"]
    migrate_schema = components["StockMigrateRequest"]
    assert migrate_schema["properties"]["data"]["$ref"] == "#/components/schemas/StockDataBlock"
