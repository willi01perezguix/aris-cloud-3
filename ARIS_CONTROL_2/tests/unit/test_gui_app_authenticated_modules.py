from __future__ import annotations

from aris_control_2.app.gui_app import GuiApp
from aris_control_2.app.gui_controller import LoginResult
from aris_control_2.app.state import SessionState


class FakeTk:
    def destroy(self) -> None:
        return

    def mainloop(self) -> None:
        return


class FakeSupportCenter:
    def __init__(self) -> None:
        self.operations: list[dict[str, object]] = []

    def record_operation(self, **payload) -> None:  # noqa: ANN003
        self.operations.append(payload)


class FakeWindow:
    def __init__(self, root, *, on_login, on_diagnostics, on_support, on_exit) -> None:  # noqa: ANN001
        self.root = root
        self.on_login = on_login
        self.on_diagnostics = on_diagnostics
        self.on_support = on_support
        self.on_exit = on_exit
        self.authenticated_view_count = 0
        self.module_handler = None
        self.module_state: dict[str, bool] = {}
        self.module_notice = ""

    def set_header(self, *, connectivity: str, base_url: str, version: str) -> None:
        return

    def set_session_context(self, *, user: str, role: str, effective_tenant_id: str) -> None:
        return

    def set_module_open_handler(self, handler) -> None:  # noqa: ANN001
        self.module_handler = handler

    def set_module_launcher_state(self, *, enabled_by_module: dict[str, bool], notice: str = "") -> None:
        self.module_state = enabled_by_module
        self.module_notice = notice

    def show_authenticated_view(self) -> None:
        self.authenticated_view_count += 1


class FakeController:
    def __init__(self, session: SessionState) -> None:
        self.session = session
        self.support_center = FakeSupportCenter()

    def status_snapshot(self) -> dict[str, str]:
        return {"connectivity": "Conectado", "base_url": "https://api.example.test", "version": "1.0.0"}

    def login(self, *, username_or_email: str, password: str) -> LoginResult:
        return LoginResult(success=True, message="ok")

    def refresh_connectivity(self):  # noqa: ANN201
        class _Connectivity:
            status = "Conectado"

        return _Connectivity()

    def diagnostic_text(self) -> str:
        return "diagnostic"

    def export_support_package(self):  # noqa: ANN201
        return ("support.json", "support.txt")


class AutoSubmitLoginDialog:
    def __init__(self, root, on_submit) -> None:  # noqa: ANN001
        self._on_submit = on_submit

    def wait(self) -> None:
        self._on_submit("demo", "secret")


def _build_app(monkeypatch, session: SessionState) -> GuiApp:
    monkeypatch.setattr("aris_control_2.app.gui_app.tk.Tk", FakeTk)
    controller = FakeController(session=session)
    return GuiApp(controller=controller, window_cls=FakeWindow, login_dialog_cls=AutoSubmitLoginDialog)


def test_authenticated_view_renders_module_buttons(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "alice"}, role="ADMIN", effective_tenant_id="tenant-a")
    app = _build_app(monkeypatch, session)

    app.open_login()

    assert app.window.authenticated_view_count == 1
    assert set(app.window.module_state.keys()) == {"tenants", "stores", "users", "stock", "transfers", "pos", "reports"}


def test_superadmin_without_tenant_disables_operational_modules(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "root"}, role="SUPERADMIN", effective_tenant_id=None)
    app = _build_app(monkeypatch, session)

    app.open_login()

    assert app.window.module_notice == "Selecciona tenant para habilitar módulos operativos."
    assert app.window.module_state["tenants"] is True
    for module in ("stores", "users", "stock", "transfers", "pos", "reports"):
        assert app.window.module_state[module] is False


def test_superadmin_with_tenant_enables_operational_modules(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "root"}, role="SUPERADMIN", effective_tenant_id="tenant-z")
    app = _build_app(monkeypatch, session)

    app.open_login()

    for module in ("tenants", "stores", "users", "stock", "transfers", "pos", "reports"):
        assert app.window.module_state[module] is True


def test_module_button_updates_current_module_and_operation_log(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "alice"}, role="ADMIN", effective_tenant_id="tenant-a")
    app = _build_app(monkeypatch, session)
    app.open_login()

    app.window.module_handler("reports")

    assert app.controller.session.current_module == "reports"
    assert app.controller.support_center.operations[-1] == {
        "module": "reports",
        "screen": "launcher",
        "action": "open",
        "result": "success",
        "latency_ms": 0,
        "code": "OK",
        "message": "module reports open",
    }
