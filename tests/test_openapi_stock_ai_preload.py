from app.main import create_app


def test_stock_ai_preload_endpoints_are_published_in_openapi():
    paths = create_app().openapi()["paths"]
    assert "/aris3/stock/ai/preload/analyze" in paths
    assert "post" in paths["/aris3/stock/ai/preload/analyze"]
    assert "/aris3/stock/ai/preload/{extraction_id}" in paths
    assert "get" in paths["/aris3/stock/ai/preload/{extraction_id}"]
    assert "/aris3/stock/ai/preload/confirm" in paths
    assert "post" in paths["/aris3/stock/ai/preload/confirm"]


def test_stock_ai_preload_files_schema_uses_binary_uploads():
    openapi = create_app().openapi()
    body_schema = openapi["components"]["schemas"]["Body_analyze_ai_preload_aris3_stock_ai_preload_analyze_post"]
    files_schema = body_schema["properties"]["files"]["anyOf"][0]
    assert files_schema["type"] == "array"
    assert files_schema["items"]["type"] == "string"
    assert files_schema["items"]["format"] == "binary"
