from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientFeatureFlags:
    navigation_shell_v110: bool = True
    tenant_switcher_v110: bool = True
    diagnostics_module_enabled: bool = True
    incidents_module_enabled: bool = True
    support_export_enabled: bool = True

    @classmethod
    def from_env(cls) -> "ClientFeatureFlags":
        return cls(
            navigation_shell_v110=_read_bool("ARIS_UI_NAV_SHELL_V110", default=True),
            tenant_switcher_v110=_read_bool("ARIS_UI_TENANT_SWITCHER_V110", default=True),
            diagnostics_module_enabled=_read_bool("ARIS_UI_DIAGNOSTICS_ENABLED", default=True),
            incidents_module_enabled=_read_bool("ARIS_UI_INCIDENTS_ENABLED", default=True),
            support_export_enabled=_read_bool("ARIS_UI_SUPPORT_EXPORT_ENABLED", default=True),
        )

    def enabled_modules(self) -> dict[str, bool]:
        return {
            "admin_core": True,
            "diagnostics": self.diagnostics_module_enabled,
            "incidents": self.incidents_module_enabled,
            "support_export": self.support_export_enabled,
        }


def _read_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
