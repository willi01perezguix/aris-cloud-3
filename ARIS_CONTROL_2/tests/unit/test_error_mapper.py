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


def test_error_mapper_maps_http_status_buckets() -> None:
    validation_payload = ErrorMapper.to_payload(
        APIError(code="HTTP_ERROR", message="invalid", status_code=422, trace_id="trace-422")
    )
    conflict_payload = ErrorMapper.to_payload(
        APIError(code="HTTP_ERROR", message="conflict", status_code=409, trace_id="trace-409")
    )

    assert validation_payload["code"] == "VALIDATION_ERROR"
    assert validation_payload["trace_id"] == "trace-422"
    assert conflict_payload["code"] == "IDEMPOTENCY_CONFLICT"
    assert conflict_payload["trace_id"] == "trace-409"
