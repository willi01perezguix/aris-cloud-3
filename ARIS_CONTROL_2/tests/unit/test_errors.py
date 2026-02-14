import httpx

from clients.aris3_client_sdk.errors import ApiError


def test_api_error_from_envelope() -> None:
    request = httpx.Request("GET", "https://example.com/aris3/me")
    response = httpx.Response(
        401,
        request=request,
        json={
            "code": "AUTH_INVALID_TOKEN",
            "message": "Invalid token",
            "details": {"reason": "expired"},
            "trace_id": "trace-body-1",
        },
    )

    error = ApiError.from_http_response(response)

    assert error.status_code == 401
    assert error.code == "AUTH_INVALID_TOKEN"
    assert error.message == "Invalid token"
    assert error.details == {"reason": "expired"}
    assert error.trace_id == "trace-body-1"


def test_api_error_fallback_non_json_uses_header_trace_id() -> None:
    request = httpx.Request("GET", "https://example.com/aris3/me")
    response = httpx.Response(
        502,
        request=request,
        text="bad gateway",
        headers={"X-Trace-ID": "trace-header-1"},
    )

    error = ApiError.from_http_response(response)

    assert error.status_code == 502
    assert error.code == "HTTP_ERROR"
    assert error.message == "bad gateway"
    assert error.trace_id == "trace-header-1"
