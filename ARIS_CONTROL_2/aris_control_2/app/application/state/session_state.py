from dataclasses import dataclass, field

from aris_control_2.app.domain.models.session_context import SessionContext


@dataclass
class SessionState:
    context: SessionContext = field(default_factory=SessionContext)
    stores_cache: list = field(default_factory=list)
    users_cache: list = field(default_factory=list)

    def clear_tenant_scoped_data(self) -> None:
        self.stores_cache.clear()
        self.users_cache.clear()
