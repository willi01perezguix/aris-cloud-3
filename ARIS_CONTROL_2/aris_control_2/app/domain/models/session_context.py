from dataclasses import dataclass, field

from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy


@dataclass
class SessionContext:
    actor_role: str | None = None
    token_tenant_id: str | None = None
    selected_tenant_id: str | None = None
    effective_tenant_id: str | None = None
    effective_permissions: list[str] = field(default_factory=list)
    must_change_password: bool = False

    def refresh_effective_tenant(self) -> None:
        self.effective_tenant_id = TenantContextPolicy.resolve_effective_tenant_id(self)

    def can(self, permission: str) -> bool:
        return permission in self.effective_permissions
