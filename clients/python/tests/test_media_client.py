from __future__ import annotations

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.media_client import MediaClient
from aris3_client_sdk.exceptions import ForbiddenError, NotFoundError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.tracing import TraceContext


def _http(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


@responses.activate
def test_media_resolve_variant_success(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={
            "meta": {"page": 1, "page_size": 1},
            "rows": [
                {
                    "sku": "SKU-1",
                    "var1_value": "Blue",
                    "var2_value": "L",
                    "image_url": "https://cdn/full.jpg",
                    "image_thumb_url": "https://cdn/thumb.jpg",
                    "image_source": "VARIANT",
                }
            ],
            "totals": {"total_rows": 1, "total_rfid": 0, "total_pending": 0, "total_units": 0},
        },
        status=200,
    )
    client = MediaClient(http=_http("https://api.example.com"), access_token="token")
    payload = client.resolve_for_variant("SKU-1", "Blue", "L")
    assert payload.source == "VARIANT"
    assert payload.resolved.thumb_url == "https://cdn/thumb.jpg"


@responses.activate
def test_media_resolve_falls_back_to_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={
            "meta": {"page": 1, "page_size": 1},
            "rows": [],
            "totals": {"total_rows": 0, "total_rfid": 0, "total_pending": 0, "total_units": 0},
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={
            "meta": {"page": 1, "page_size": 1},
            "rows": [],
            "totals": {"total_rows": 0, "total_rfid": 0, "total_pending": 0, "total_units": 0},
        },
        status=200,
    )
    client = MediaClient(http=_http("https://api.example.com"), access_token="token")
    payload = client.resolve_for_variant("SKU-1", "Blue", "L")
    assert payload.source == "PLACEHOLDER"


@responses.activate
def test_media_error_trace_id_propagates(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={"code": "FORBIDDEN", "message": "denied", "details": {}, "trace_id": "trace-403"},
        status=403,
    )
    client = MediaClient(http=_http("https://api.example.com"), access_token="token")
    try:
        client.resolve_for_variant("SKU-1", "Blue", "L")
    except ForbiddenError as exc:
        assert exc.trace_id == "trace-403"
    else:
        raise AssertionError("Expected ForbiddenError")


@responses.activate
def test_media_not_found_mapping(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/media/assets",
        json={"code": "NOT_FOUND", "message": "missing", "details": {}, "trace_id": "trace-404"},
        status=404,
    )
    client = MediaClient(http=_http("https://api.example.com"), access_token="token")
    try:
        client.list_assets()
    except NotFoundError:
        pass
    else:
        raise AssertionError("Expected NotFoundError")
