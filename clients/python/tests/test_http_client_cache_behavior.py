from __future__ import annotations

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


@responses.activate
def test_request_get_use_get_cache_false_skips_read_and_write(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")

    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={"value": 1},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={"value": 2},
        status=200,
    )

    first = http.request("GET", "/aris3/reports/overview", use_get_cache=False)
    second = http.request("GET", "/aris3/reports/overview", use_get_cache=False)

    assert first == {"value": 1}
    assert second == {"value": 2}
    assert len(responses.calls) == 2
    assert http._cache == {}


@responses.activate
def test_request_get_use_get_cache_true_preserves_current_behavior(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")

    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={"value": 1},
        status=200,
    )

    first = http.request("GET", "/aris3/reports/overview", use_get_cache=True)
    second = http.request("GET", "/aris3/reports/overview", use_get_cache=True)

    assert first == {"value": 1}
    assert second == {"value": 1}
    assert len(responses.calls) == 1
    assert len(http._cache or {}) == 1


@responses.activate
def test_request_get_use_get_cache_false_ignores_existing_cache(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    cache_key = http._cache_key("GET", "https://api.example.com/aris3/reports/overview", {"Accept": "application/json"}, None)
    assert cache_key is not None
    http._cache[cache_key] = (9999999999.0, {"value": 111})

    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={"value": 222},
        status=200,
    )

    response = http.request("GET", "/aris3/reports/overview", use_get_cache=False)

    assert response == {"value": 222}
    assert len(responses.calls) == 1
    assert http._cache[cache_key][1] == {"value": 111}
