from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


def test_error_mapper_formats_api_error() -> None:
    error = APIError(code="INVALID", message="Invalid request", details=None, trace_id="trace-1")

    assert ErrorMapper.to_display_message(error) == "[INVALID] Invalid request (trace_id=trace-1)"
