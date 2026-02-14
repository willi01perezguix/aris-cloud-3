from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


def test_error_mapper_formats_api_error_with_known_code() -> None:
    error = APIError(code="TENANT_CONTEXT_REQUIRED", message="Backend raw msg", details=None, trace_id="trace-1")

    assert (
        ErrorMapper.to_display_message(error)
        == "[TENANT_CONTEXT_REQUIRED] Selecciona un tenant para continuar. (trace_id=trace-1)"
    )


def test_error_mapper_falls_back_to_backend_message_for_unknown_code() -> None:
    error = APIError(code="UNKNOWN", message="Backend raw msg", details=None, trace_id="trace-2")

    assert ErrorMapper.to_display_message(error) == "[UNKNOWN] Backend raw msg (trace_id=trace-2)"
