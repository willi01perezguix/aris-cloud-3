from dataclasses import dataclass, field

from aris_control_2.app.domain.models.session_context import SessionContext


@dataclass
class SessionState:
    context: SessionContext = field(default_factory=SessionContext)
    stores_cache: list = field(default_factory=list)
    users_cache: list = field(default_factory=list)
    stores_filter: str = ""
    users_filter: str = ""
    selected_store_row: str | None = None
    selected_user_store_id: str | None = None
    selected_user_row: str | None = None
    stores_page: int = 1
    users_page: int = 1
    mutation_in_flight: set[str] = field(default_factory=set)
    pending_mutations: dict[str, dict[str, str]] = field(default_factory=dict)
    last_admin_action: dict[str, str] | None = None

    def clear_tenant_scoped_data(self) -> None:
        self.stores_cache.clear()
        self.users_cache.clear()
        self.stores_filter = ""
        self.users_filter = ""
        self.selected_store_row = None
        self.selected_user_store_id = None
        self.selected_user_row = None
        self.stores_page = 1
        self.users_page = 1
