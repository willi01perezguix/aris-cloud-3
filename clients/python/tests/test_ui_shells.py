from __future__ import annotations

from aris_core_3_app.app import CoreAppShell, build_menu_items as build_core_menu
from aris_control_center_app.app import ControlCenterAppShell, build_menu_items as build_control_menu


def test_core_app_shell_headless() -> None:
    app = CoreAppShell()
    app.start(headless=True)


def test_control_center_app_shell_headless() -> None:
    app = ControlCenterAppShell()
    app.start(headless=True)


def test_core_menu_permissions() -> None:
    allowed = {"stock.view", "reports.view"}
    items = build_core_menu(allowed)
    enabled = {item.label for item in items if item.enabled}
    assert enabled == {"Stock", "Reports"}


def test_control_center_menu_permissions() -> None:
    allowed = {"users.view", "audit.view"}
    items = build_control_menu(allowed)
    enabled = {item.label for item in items if item.enabled}
    assert enabled == {"Users", "Audit"}
