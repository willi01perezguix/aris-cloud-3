from clients.aris3_client_sdk.errors import ApiError

from aris_control_2.app.gui_controller import GuiController


class StubAuthClient:
    def login(self, *, username_or_email: str, password: str) -> dict[str, str]:
        raise ApiError(
            code="AUTH_INVALID_CREDENTIALS",
            message="Credenciales inválidas",
            trace_id="trace-login-001",
            status_code=401,
        )


class StubHttpClient:
    def request(self, method: str, path: str) -> dict[str, str]:
        return {"status": "ok", "path": path}


class StubMeClient:
    def get_me(self, *, access_token: str) -> dict[str, str]:
        return {"role": "ADMIN", "effective_tenant_id": "tenant-a"}


class StubSupportCenter:
    def __init__(self) -> None:
        self.incidents: list[dict[str, str]] = []
        self.operations: list[dict[str, str]] = []

    def record_incident(self, *, module: str, payload: dict[str, str], status: str = "abierto") -> dict[str, str]:
        incident = {"module": module, "message": str(payload.get("message")), "status": status}
        self.incidents.append(incident)
        return incident

    def record_operation(self, **kwargs) -> None:  # noqa: ANN003
        self.operations.append({"module": str(kwargs.get("module", ""))})


def test_gui_controller_login_handles_api_error_without_crashing() -> None:
    support_center = StubSupportCenter()
    controller = GuiController(
        http_client=StubHttpClient(),
        auth_client=StubAuthClient(),
        me_client=StubMeClient(),
        support_center=support_center,
    )

    result = controller.login(username_or_email="demo", password="bad")

    assert result.success is False
    assert result.trace_id == "trace-login-001"
    assert "inválidas" in result.message
    assert support_center.incidents
