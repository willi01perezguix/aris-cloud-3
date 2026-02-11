from __future__ import annotations

from dataclasses import dataclass

from apps.control_center.ui.widgets.permissioned_actions import gate_permission


@dataclass(frozen=True)
class NavItem:
    label: str
    permission: str


CONTROL_CENTER_NAV: tuple[NavItem, ...] = (
    NavItem("Users", "USER_MANAGE"),
    NavItem("Access Control", "ACCESS_CONTROL_VIEW"),
    NavItem("Settings: Variant Fields", "SETTINGS_MANAGE"),
    NavItem("Settings: Return Policy", "SETTINGS_MANAGE"),
)


def build_navigation(allowed_permissions: set[str]) -> list[tuple[NavItem, bool, str | None]]:
    return [
        (item, gate.allowed, gate.reason)
        for item in CONTROL_CENTER_NAV
        for gate in [gate_permission(allowed_permissions, item.permission, deny_message="Missing permission")]
    ]
