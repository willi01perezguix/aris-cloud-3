from app.main import create_app


def test_stock_ai_preload_endpoints_are_published_in_openapi():
    paths = create_app().openapi()["paths"]
    assert "/aris3/stock/ai/preload/analyze" in paths
    assert "post" in paths["/aris3/stock/ai/preload/analyze"]
    assert "/aris3/stock/ai/preload/{extraction_id}" in paths
    assert "get" in paths["/aris3/stock/ai/preload/{extraction_id}"]
    assert "/aris3/stock/ai/preload/confirm" in paths
    assert "post" in paths["/aris3/stock/ai/preload/confirm"]
