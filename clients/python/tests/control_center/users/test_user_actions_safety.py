from __future__ import annotations

from apps.control_center.app.navigation import build_navigation
from apps.control_center.ui.users.user_actions_dialog import UserActionGuard, action_dedupe_key, requires_confirmation
from apps.control_center.ui.users.users_list_view import UsersListViewModel


def test_high_impact_actions_confirmation_in_flight_and_dedupe() -> None:
    assert requires_confirmation("set_role") is True
    guard = UserActionGuard(user_id="u-1", action="set_role", reason="incident follow-up")
    key = action_dedupe_key("u-1", "set_role", "txn-1")
    assert guard.can_submit(key) is True
    guard.mark_submitted(key)
    assert guard.can_submit(key) is False
    guard.complete(success=False, trace_id="trace-1")
    rendered = guard.notifications.render()
    assert rendered["count"] == 1
    assert rendered["messages"][0]["trace_id"] == "trace-1"


def test_permission_gated_controls_default_deny() -> None:
    nav = build_navigation({"USER_MANAGE"})
    by_label = {item.label: allowed for item, allowed, _ in nav}
    assert by_label["Access Control"] is False


def test_users_table_state_productivity_helpers() -> None:
    vm = UsersListViewModel(
        users=[
            {"id": "2", "username": "bob", "email": "b@x", "role": "MANAGER"},
            {"id": "1", "username": "alice", "email": "a@x", "role": "ADMIN"},
        ],
        query="",
        selected_user_id="1",
    )
    assert [u["username"] for u in vm.filtered] == ["alice", "bob"]
    assert vm.paged()["total_pages"] == 1
    assert vm.focus_order()[0] == "search"
    assert "alice" in (vm.selected_summary()["summary"] or "")
