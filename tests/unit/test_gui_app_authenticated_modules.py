from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "clients/python/aris3_client_sdk/src"))
sys.path.insert(0, str(ROOT / "clients/python/aris_control_center_app/src"))

from aris_control_center_app import app as app_module


class FakeWidget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.children: list[FakeWidget] = []
        self.text = kwargs.get("text", "")
        self.state = kwargs.get("state")
        self.command = kwargs.get("command")
        self.textvariable = kwargs.get("textvariable")
        if parent is not None and hasattr(parent, "children"):
            parent.children.append(self)

    def pack(self, **kwargs):
        return None

    def grid(self, **kwargs):
        return None

    def destroy(self):
        if self.parent is not None and hasattr(self.parent, "children") and self in self.parent.children:
            self.parent.children.remove(self)

    def winfo_children(self):
        return list(self.children)

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]

    def columnconfigure(self, *_args, **_kwargs):
        return None


class FakeFrame(FakeWidget):
    pass


class FakeLabel(FakeWidget):
    pass


class FakeEntry(FakeWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._value = ""

    def get(self):
        return self._value


class FakeButton(FakeWidget):
    pass


class FakeLabelFrame(FakeFrame):
    pass


class FakeRoot:
    def __init__(self):
        self.children: list[FakeWidget] = []

    def winfo_children(self):
        return list(self.children)

    def title(self, *_args, **_kwargs):
        return None

    def deiconify(self):
        return None

    def mainloop(self):
        return None


def walk_texts(node) -> list[str]:
    values: list[str] = []
    for child in node.winfo_children():
        if getattr(child, "text", ""):
            values.append(child.text)
        values.extend(walk_texts(child))
    return values


class FakeSession:
    def __init__(self):
        self.token = None
        self.user = None

    def _http(self):
        return object()

    def establish(self, token, user):
        self.token = token.access_token
        self.user = user

    def logout(self):
        self.token = None
        self.user = None


def _make_app(monkeypatch: pytest.MonkeyPatch) -> app_module.ControlCenterAppShell:
    fake_ttk = SimpleNamespace(
        Frame=FakeFrame,
        Label=FakeLabel,
        Entry=FakeEntry,
        Button=FakeButton,
        LabelFrame=FakeLabelFrame,
    )
    monkeypatch.setattr(app_module, "ttk", fake_ttk)
    session = FakeSession()
    shell = app_module.ControlCenterAppShell(config=SimpleNamespace(env_name="test"), session=session)
    shell.root = FakeRoot()
    return shell


def _stub_auth_ok(monkeypatch: pytest.MonkeyPatch):
    class MockAuthClient:
        def __init__(self, http, access_token=None):
            self.access_token = access_token

        def login(self, username, password):
            return SimpleNamespace(access_token="tok-123")

        def me(self):
            return SimpleNamespace(id="u-1", username="demo", role="admin", tenant_id="tenant-a")

    class MockAccessControlClient:
        def __init__(self, http, access_token=None):
            self.access_token = access_token

        def effective_permissions(self):
            return SimpleNamespace(
                permissions=[
                    SimpleNamespace(key="tenants.view", allowed=True),
                    SimpleNamespace(key="stores.view", allowed=True),
                    SimpleNamespace(key="users.view", allowed=True),
                    SimpleNamespace(key="stock.view", allowed=True),
                    SimpleNamespace(key="transfers.view", allowed=True),
                    SimpleNamespace(key="pos.view", allowed=True),
                    SimpleNamespace(key="reports.view", allowed=True),
                ]
            )

    monkeypatch.setattr(app_module, "AuthClient", MockAuthClient)
    monkeypatch.setattr(app_module, "AccessControlClient", MockAccessControlClient)


def test_login_success_navigates_to_authenticated_shell(monkeypatch: pytest.MonkeyPatch):
    shell = _make_app(monkeypatch)
    _stub_auth_ok(monkeypatch)

    shell._login("demo", "pass")

    assert shell.current_screen == "authenticated"


def test_authenticated_shell_renders_module_buttons(monkeypatch: pytest.MonkeyPatch):
    shell = _make_app(monkeypatch)
    _stub_auth_ok(monkeypatch)

    shell._login("demo", "pass")

    labels = [button.text for button in shell.menu_buttons]
    assert labels == ["Tenants", "Stores", "Users", "Stock", "Transfers", "POS", "Reports", "Logout"]


def test_module_button_opens_placeholder_view(monkeypatch: pytest.MonkeyPatch):
    shell = _make_app(monkeypatch)
    _stub_auth_ok(monkeypatch)
    shell._login("demo", "pass")

    shell._open_module("Stores")

    assert shell.current_screen == "module"
    assert shell.active_module == "Stores"
    texts = walk_texts(shell.content_frame)
    assert "Stores" in texts
    assert "Volver" in texts


def test_logout_returns_to_public_home(monkeypatch: pytest.MonkeyPatch):
    shell = _make_app(monkeypatch)
    _stub_auth_ok(monkeypatch)
    shell._login("demo", "pass")

    shell._logout()

    assert shell.current_screen == "login"
    assert "ARIS Control Center Login" in walk_texts(shell.root)
