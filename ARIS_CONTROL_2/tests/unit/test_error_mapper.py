from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


def test_error_mapper_known_codes_and_suggestion() -> None:
    payload = ErrorMapper.to_payload(
        APIError(code="PERMISSION_DENIED", message="raw", trace_id="trace-1", details={"field": "x"})
    )

    assert payload["code"] == "PERMISSION_DENIED"
    assert payload["trace_id"] == "trace-1"
    assert payload["suggestion"]
    assert payload["message"] != "raw"


def test_error_mapper_fallback_internal_error() -> None:
    payload = ErrorMapper.to_payload(RuntimeError("boom"))

    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["suggestion"]
