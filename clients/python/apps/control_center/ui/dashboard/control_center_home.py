from __future__ import annotations

from apps.control_center.app.navigation import build_navigation


def home_summary(actor: str, allowed_permissions: set[str]) -> dict:
    return {
        "actor": actor,
        "nav": build_navigation(allowed_permissions),
        "permission_count": len(allowed_permissions),
    }
