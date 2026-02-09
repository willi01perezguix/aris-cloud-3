from __future__ import annotations

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.stock_client import StockClient, build_stock_params
from aris3_client_sdk.exceptions import ForbiddenError, UnauthorizedError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.models_stock import StockQuery, StockTableResponse
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


def test_stock_query_param_serialization() -> None:
    query = StockQuery(
        q="Blue",
        sku=None,
        from_date="2024-01-01T00:00:00Z",
        to_date=None,
        page=2,
        sort_order="asc",
    )
    params = build_stock_params(query)
    assert params["q"] == "Blue"
    assert params["from"] == "2024-01-01T00:00:00Z"
    assert params["page"] == 2
    assert params["sort_dir"] == "asc"
    assert "sku" not in params
    assert "to" not in params


def test_stock_response_parsing_with_images() -> None:
    payload = {
        "meta": {"page": 1, "page_size": 50, "sort_by": "created_at", "sort_dir": "desc"},
        "rows": [
            {
                "id": "1",
                "tenant_id": "tenant",
                "sku": "SKU-1",
                "description": "Blue",
                "var1_value": "Blue",
                "var2_value": "M",
                "epc": "EPC1",
                "location_code": "LOC",
                "pool": "P1",
                "status": "ACTIVE",
                "location_is_vendible": True,
                "image_asset_id": "asset-1",
                "image_url": "https://example.com/img.jpg",
                "image_thumb_url": "https://example.com/thumb.jpg",
                "image_source": "cdn",
                "image_updated_at": "2024-01-01T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "extra_field": "extra",
            }
        ],
        "totals": {"total_rows": 1, "total_rfid": 1, "total_pending": 0, "total_units": 1},
        "extra_meta": "extra",
    }
    response = StockTableResponse.model_validate(payload)
    assert response.rows[0].image_url == "https://example.com/img.jpg"
    assert response.rows[0].image_thumb_url == "https://example.com/thumb.jpg"


@responses.activate
def test_stock_client_success(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={
            "meta": {"page": 1, "page_size": 50, "sort_by": "created_at", "sort_dir": "desc"},
            "rows": [],
            "totals": {"total_rows": 0, "total_rfid": 0, "total_pending": 0, "total_units": 0},
        },
        status=200,
    )
    client = StockClient(http=http, access_token="token")
    response = client.get_stock(StockQuery(page=1))
    assert response.meta.page == 1
    assert response.totals.total_rows == 0


@responses.activate
def test_stock_client_auth_errors(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={"code": "INVALID_TOKEN", "message": "no", "details": None, "trace_id": "trace"},
        status=401,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={"code": "PERMISSION_DENIED", "message": "no", "details": None, "trace_id": "trace"},
        status=403,
    )
    client = StockClient(http=http, access_token="bad")
    try:
        client.get_stock(StockQuery(page=1))
    except UnauthorizedError:
        pass
    else:
        raise AssertionError("Expected UnauthorizedError")

    try:
        client.get_stock(StockQuery(page=1))
    except ForbiddenError:
        pass
    else:
        raise AssertionError("Expected ForbiddenError")
