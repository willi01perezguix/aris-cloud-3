from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


def _error(code: str) -> APIError:
    return APIError(code=code, message="Backend raw", details={"field": "x"}, trace_id="trace-1")


def test_error_mapper_known_codes() -> None:
    for code in [
        "TENANT_STORE_MISMATCH",
        "PERMISSION_DENIED",
        "TENANT_CONTEXT_REQUIRED",
        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
    ]:
        payload = ErrorMapper.to_payload(_error(code))
        assert payload["code"] == code
        assert payload["trace_id"] == "trace-1"
        assert payload["message"] != "Backend raw"


def test_error_mapper_display_includes_trace_id() -> None:
    message = ErrorMapper.to_display_message(_error("PERMISSION_DENIED"))

    assert "trace_id=trace-1" in message
