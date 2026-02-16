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
        self.home_view_count = 0
        self.module_handler = None
        self.logout_handler = None
        self.module_state: dict[str, bool] = {}
        self.module_notice = ""
        self.placeholder_module_label = ""

    def set_header(self, *, connectivity: str, base_url: str, version: str) -> None:
        return

    def set_session_context(self, *, user: str, role: str, effective_tenant_id: str) -> None:
        return

    def set_module_open_handler(self, handler) -> None:  # noqa: ANN001
        self.module_handler = handler

    def set_logout_handler(self, handler) -> None:  # noqa: ANN001
        self.logout_handler = handler

    def set_module_launcher_state(self, *, enabled_by_module: dict[str, bool], notice: str = "") -> None:
        self.module_state = enabled_by_module
        self.module_notice = notice

    def show_authenticated_view(self) -> None:
        self.authenticated_view_count += 1

    def show_module_placeholder(self, *, module_label: str) -> None:
        self.placeholder_module_label = module_label

    def show_home_view(self) -> None:
        self.home_view_count += 1


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


def test_login_success_navigates_to_authenticated_shell(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "alice"}, role="ADMIN", effective_tenant_id="tenant-a")
    app = _build_app(monkeypatch, session)

    app.open_login()

    assert app.window.authenticated_view_count == 1


def test_authenticated_shell_renders_only_control2_modules(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "alice"}, role="ADMIN", effective_tenant_id="tenant-a")
    app = _build_app(monkeypatch, session)

    app.open_login()

    assert set(app.window.module_state.keys()) == {"tenants", "stores", "users"}


def test_module_button_opens_placeholder_view(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "alice"}, role="ADMIN", effective_tenant_id="tenant-a")
    app = _build_app(monkeypatch, session)
    app.open_login()

    app.window.module_handler("users")

    assert app.window.placeholder_module_label == "Users"


def test_disallowed_module_is_blocked_and_warns(monkeypatch) -> None:
    warnings: list[dict[str, object]] = []

    def _fake_showwarning(title: str, message: str, parent=None):  # noqa: ANN001
        warnings.append({"title": title, "message": message, "parent": parent})
        return "ok"

    monkeypatch.setattr("aris_control_2.app.gui_app.messagebox.showwarning", _fake_showwarning)

    session = SessionState(access_token="token", user={"username": "alice"}, role="ADMIN", effective_tenant_id="tenant-a")
    app = _build_app(monkeypatch, session)
    app.open_login()

    app.window.module_handler("reports")

    assert app.window.placeholder_module_label == ""
    assert warnings
    assert "no esta habilitado" in str(warnings[0]["message"]).lower()
    assert app.controller.support_center.operations[-1]["result"] == "blocked"
    assert app.controller.support_center.operations[-1]["code"] == "MODULE_NOT_ENABLED"


def test_superadmin_without_tenant_disables_stores_users(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "root"}, role="SUPERADMIN", effective_tenant_id=None)
    app = _build_app(monkeypatch, session)

    app.open_login()

    assert app.window.module_state["tenants"] is True
    assert app.window.module_state["stores"] is False
    assert app.window.module_state["users"] is False
    assert "Selecciona tenant" in app.window.module_notice


def test_logout_returns_to_public_home(monkeypatch) -> None:
    session = SessionState(access_token="token", user={"username": "alice"}, role="ADMIN", effective_tenant_id="tenant-a")
    app = _build_app(monkeypatch, session)
    app.open_login()

    app.window.logout_handler()

    assert app.controller.session.is_authenticated() is False
    assert app.window.home_view_count == 1



