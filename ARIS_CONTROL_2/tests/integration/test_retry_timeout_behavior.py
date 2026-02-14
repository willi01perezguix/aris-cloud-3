import httpx

from aris_control_2.clients.aris3_client_sdk.http_client import APIError, HttpClient


class _Transport:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def __call__(self, *args, **kwargs):
        result = self.responses[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


def _response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=payload)


def test_retry_on_5xx_and_timeout() -> None:
    transport = _Transport(
        [
            httpx.ReadTimeout("timeout"),
            _response(503, {"code": "INTERNAL_ERROR", "message": "down"}),
            _response(200, {"ok": True}),
        ]
    )
    client = HttpClient("http://x", retry_max_attempts=3, retry_backoff_ms=0, transport=transport)

    payload = client.request("GET", "/health")

    assert payload["ok"] is True
    assert transport.calls == 3


def test_no_retry_on_4xx() -> None:
    transport = _Transport([_response(403, {"code": "PERMISSION_DENIED", "message": "no"})])
    client = HttpClient("http://x", retry_max_attempts=3, retry_backoff_ms=0, transport=transport)

    try:
        client.request("GET", "/x")
        raised = False
    except APIError as error:
        raised = True
        assert error.code == "PERMISSION_DENIED"

    assert raised
    assert transport.calls == 1
