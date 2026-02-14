from datetime import datetime

from clients.aris3_client_sdk.errors import ApiError

from aris_control_2.app.diagnostics import ConnectivityResult
from aris_control_2.app.main import _api_diagnostics, _print_startup_connectivity_status


class StubHttpClient:
    def __init__(self, fail_ready: bool = False) -> None:
        self.fail_ready = fail_ready

    def request(self, method: str, path: str):
        if path == "/ready" and self.fail_ready:
            raise ApiError(code="NETWORK_ERROR", message="timeout", status_code=None, trace_id="trace-ready")
        return {"status": "ok", "path": path}


def test_api_diagnostics_reports_ok_checks() -> None:
    results = _api_diagnostics(StubHttpClient())

    assert [entry["check"] for entry in results] == ["health", "ready"]
    assert all(entry["status"] == "OK" for entry in results)


def test_api_diagnostics_reports_errors_without_crashing() -> None:
    results = _api_diagnostics(StubHttpClient(fail_ready=True))

    ready_entry = next(entry for entry in results if entry["check"] == "ready")
    assert ready_entry["status"] == "ERROR"
    assert "NETWORK_ERROR" in ready_entry["details"]


def test_startup_connectivity_status_messages(capsys) -> None:
    _print_startup_connectivity_status(
        ConnectivityResult(status="Sin conexión", latency_ms=None, checked_at=datetime.now().astimezone(), message="timeout")
    )

    output = capsys.readouterr().out
    assert "Estado startup: ❌ Sin conexión." in output
    assert "opción 0 para reintentar" in output
