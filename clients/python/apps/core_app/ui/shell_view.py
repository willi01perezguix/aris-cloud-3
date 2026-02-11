from __future__ import annotations

from dataclasses import dataclass

from app.navigation import ModuleSpec
from app.state import SessionContext


@dataclass
class ShellPlaceholder:
    module: ModuleSpec
    session: SessionContext

    def render(self) -> dict[str, str | tuple[str, ...] | None]:
        return {
            "module_name": self.module.label,
            "status": "Ready for integration in next sprint days",
            "user": self.session.user.username if self.session.user else None,
            "tenant": self.session.tenant_id,
            "store": self.session.store_id,
            "required_permissions": self.module.required_permissions,
        }
