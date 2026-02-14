from clients.aris3_client_sdk.errors import ApiError

from aris_control_2.app.admin_console import _api_error_diagnostic


def test_api_error_diagnostic_for_network_error() -> None:
    error = ApiError(code="NETWORK_ERROR", message="net down", status_code=None)

    diagnostic = _api_error_diagnostic(error)

    assert "No se pudo conectar" in diagnostic


def test_api_error_diagnostic_for_auth_error() -> None:
    error = ApiError(code="HTTP_ERROR", message="unauthorized", status_code=401)

    diagnostic = _api_error_diagnostic(error)

    assert "Sesión expirada" in diagnostic
