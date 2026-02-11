from __future__ import annotations

from dataclasses import dataclass, field

from apps.control_center.ui.widgets.table_state_helpers import TableState, selected_row_summary


@dataclass
class UsersListViewModel:
    users: list[dict]
    query: str = ""
    table_state: TableState = field(default_factory=TableState)
    selected_user_id: str | None = None

    @property
    def filtered(self) -> list[dict]:
        rows = self.users
        if self.query:
            query = self.query.lower()
            rows = [u for u in rows if query in u.get("username", "").lower() or query in u.get("email", "").lower()]
        rows = self.table_state.apply_filters(rows)
        rows = self.table_state.stable_sort(rows)
        return rows

    def paged(self) -> dict[str, object]:
        return self.table_state.paginate(self.filtered)

    def focus_order(self) -> list[str]:
        return ["search", "filters", "table", "row_actions", "pagination"]

    def selected_summary(self) -> dict[str, str | None]:
        selected = next((u for u in self.users if str(u.get("id")) == str(self.selected_user_id)), None)
        return selected_row_summary(selected)
