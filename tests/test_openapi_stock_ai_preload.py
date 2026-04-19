from app.main import create_app


def test_stock_ai_preload_endpoints_are_published_in_openapi():
    paths = create_app().openapi()["paths"]
    assert "/aris3/stock/ai/preload/analyze" in paths
    assert "post" in paths["/aris3/stock/ai/preload/analyze"]
    assert "/aris3/stock/ai/preload/{extraction_id}" in paths
    assert "get" in paths["/aris3/stock/ai/preload/{extraction_id}"]
    assert "/aris3/stock/ai/preload/confirm" in paths
    assert "post" in paths["/aris3/stock/ai/preload/confirm"]
    assert "/aris3/catalog/products/upsert" in paths
    assert "/aris3/catalog/products/bulk-upsert" in paths


def test_stock_ai_preload_files_schema_uses_binary_uploads():
    openapi = create_app().openapi()
    body_schema = openapi["components"]["schemas"]["Body_analyze_ai_preload_aris3_stock_ai_preload_analyze_post"]
    files_schema = body_schema["properties"]["files"]["anyOf"][0]
    assert files_schema["type"] == "array"
    assert files_schema["items"]["type"] == "string"
    assert files_schema["items"]["format"] == "binary"


def test_stock_ai_preload_line_schema_includes_extended_normalized_fields():
    openapi = create_app().openapi()
    line_schema = openapi["components"]["schemas"]["AiPreloadLine"]["properties"]
    for field in (
        "reference_price_original",
        "reference_price_gtq",
        "logistics_status",
        "source_order_number",
        "source_order_date",
        "brand",
        "category",
        "style",
    ):
        assert field in line_schema


def test_ai_confirm_request_includes_confirm_mode():
    openapi = create_app().openapi()
    props = openapi["components"]["schemas"]["AiPreloadConfirmRequest"]["properties"]
    assert "confirm_mode" in props
