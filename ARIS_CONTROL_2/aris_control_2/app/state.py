from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    access_token: str | None = None
    refresh_token: str | None = None
    must_change_password: bool = False
    user: dict[str, Any] | None = None
    role: str | None = None
    effective_tenant_id: str | None = None
    selected_tenant_id: str | None = None
    filters_by_module: dict[str, dict[str, str]] = field(default_factory=dict)
    pagination_by_module: dict[str, dict[str, int]] = field(default_factory=dict)
    listing_view_by_module: dict[str, dict[str, Any]] = field(default_factory=dict)
    current_module: str = "menu_principal"

    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    def apply_me(self, me_payload: dict[str, Any]) -> None:
        self.user = me_payload
        self.role = str(me_payload.get("role") or me_payload.get("actor_role") or "").upper() or None
        self.effective_tenant_id = (
            me_payload.get("effective_tenant_id")
            or me_payload.get("tenant_id")
            or me_payload.get("actor_tenant_id")
        )
        if self.role != "SUPERADMIN":
            self.selected_tenant_id = self.effective_tenant_id

    def session_fingerprint(self) -> str:
        role = self.role or "ANON"
        tenant = self.effective_tenant_id or "NO_TENANT"
        return f"{role}:{tenant}"

    def clear(self) -> None:
        self.access_token = None
        self.refresh_token = None
        self.must_change_password = False
        self.user = None
        self.role = None
        self.effective_tenant_id = None
        self.selected_tenant_id = None
        self.filters_by_module = {}
        self.pagination_by_module = {}
        self.listing_view_by_module = {}
        self.current_module = "menu_principal"
