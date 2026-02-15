from __future__ import annotations

from aris_control_2.app.gui_app import GuiApp
from aris_control_2.app.gui_controller import LoginResult
from aris_control_2.app.state import SessionState


class FakeTk:
    def destroy(self) -> None:
        return

    def mainloop(self) -> None:
        return


class FakeWindow:
    def __init__(self, root, *, on_login, on_diagnostics, on_support, on_exit) -> None:  # noqa: ANN001
        self.root = root
        self.on_login = on_login
        self.on_diagnostics = on_diagnostics
        self.on_support = on_support
        self.on_exit = on_exit
        self.header_updates: list[dict[str, str]] = []
        self.session_context_updates: list[dict[str, str]] = []
        self.authenticated_view_count = 0

    def set_header(self, *, connectivity: str, base_url: str, version: str) -> None:
        self.header_updates.append({"connectivity": connectivity, "base_url": base_url, "version": version})

    def set_session_context(self, *, user: str, role: str, effective_tenant_id: str) -> None:
        self.session_context_updates.append({"user": user, "role": role, "effective_tenant_id": effective_tenant_id})

    def show_authenticated_view(self) -> None:
        self.authenticated_view_count += 1


class FakeController:
    def __init__(self, login_results: list[LoginResult], session: SessionState | None = None) -> None:
        self._results = list(login_results)
        self.session = session or SessionState()

    def status_snapshot(self) -> dict[str, str]:
        return {"connectivity": "Conectado", "base_url": "https://api.example.test", "version": "1.0.0"}

    def login(self, *, username_or_email: str, password: str) -> LoginResult:
        if self._results:
            return self._results.pop(0)
        return LoginResult(success=False, message="No configurado")

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


class DoubleSubmitLoginDialog:
    def __init__(self, root, on_submit) -> None:  # noqa: ANN001
        self._on_submit = on_submit

    def wait(self) -> None:
        self._on_submit("demo", "secret")
        self._on_submit("demo", "secret")


def test_login_success_navigates_to_authenticated_view(monkeypatch) -> None:
    monkeypatch.setattr("aris_control_2.app.gui_app.tk.Tk", FakeTk)
    session = SessionState()
    session.access_token = "token-123"
    session.user = {"username": "alice"}
    session.role = "ADMIN"
    session.effective_tenant_id = "tenant-a"
    controller = FakeController(login_results=[LoginResult(success=True, message="Inicio de sesión exitoso.")], session=session)

    app = GuiApp(controller=controller, window_cls=FakeWindow, login_dialog_cls=AutoSubmitLoginDialog)
    app.open_login()

    assert controller.session.access_token == "token-123"
    assert controller.session.user == {"username": "alice"}
    assert controller.session.role == "ADMIN"
    assert controller.session.effective_tenant_id == "tenant-a"
    assert app.window.authenticated_view_count == 1
    assert app.window.session_context_updates[-1] == {
        "user": "alice",
        "role": "ADMIN",
        "effective_tenant_id": "tenant-a",
    }


def test_login_failure_stays_on_home_view(monkeypatch) -> None:
    monkeypatch.setattr("aris_control_2.app.gui_app.tk.Tk", FakeTk)
    controller = FakeController(login_results=[LoginResult(success=False, message="Credenciales inválidas", trace_id="trace-1")])

    app = GuiApp(controller=controller, window_cls=FakeWindow, login_dialog_cls=AutoSubmitLoginDialog)
    app.open_login()

    assert app.window.authenticated_view_count == 0
    assert app.window.session_context_updates == []


def test_login_double_submit_does_not_open_duplicate_view(monkeypatch) -> None:
    monkeypatch.setattr("aris_control_2.app.gui_app.tk.Tk", FakeTk)
    session = SessionState(access_token="token-xyz", user={"username": "bob"}, role="MANAGER", effective_tenant_id="tenant-b")
    controller = FakeController(
        login_results=[
            LoginResult(success=True, message="Inicio de sesión exitoso."),
            LoginResult(success=True, message="Inicio de sesión exitoso."),
        ],
        session=session,
    )

    app = GuiApp(controller=controller, window_cls=FakeWindow, login_dialog_cls=DoubleSubmitLoginDialog)
    app.open_login()

    assert app.window.authenticated_view_count == 1
