from __future__ import annotations

from app.navigation import ModuleSpec
from services.permissions_service import PermissionGate


class PermissionedMenu:
    def __init__(self, modules: list[ModuleSpec], gate: PermissionGate) -> None:
        self.modules = modules
        self.gate = gate

    def visible_labels(self) -> list[str]:
        visible: list[str] = []
        for module in self.modules:
            if self.gate.allows_any(*module.required_permissions):
                visible.append(module.label)
        return visible
