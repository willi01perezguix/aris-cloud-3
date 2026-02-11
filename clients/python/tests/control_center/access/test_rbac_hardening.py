from __future__ import annotations

from apps.control_center.services.access_control_service import blocked_admin_grants, deny_wins
from apps.control_center.ui.access.effective_permissions_view import format_effective_permissions
from apps.control_center.ui.access.permissions_explainer_panel import explain_permission
from apps.control_center.ui.access.policy_diff_panel import build_policy_change_preview
from apps.control_center.ui.access.roles_policies_view import (
    block_for_admin_ceiling,
    deny_warning,
    precedence_summary,
    requires_high_impact_confirmation,
    resolve_precedence,
)


def test_rbac_precedence_and_deny_over_allow_visualization() -> None:
    assert precedence_summary().startswith("global template")
    assert deny_warning(True)
    resolved = resolve_precedence({"A", "B"}, {"A"})
    assert resolved["A"] is False
    assert deny_wins([
        {"key": "A", "allowed": True, "source": "template_allow"},
        {"key": "A", "allowed": False, "source": "tenant_deny"},
    ])["A"] is False


def test_admin_ceiling_blocking_feedback() -> None:
    blocked = blocked_admin_grants({"AUDIT_VIEW"}, {"AUDIT_VIEW", "USER_MANAGE"})
    assert blocked == {"USER_MANAGE"}
    feedback = block_for_admin_ceiling({"AUDIT_VIEW"}, {"USER_MANAGE"})
    assert "tenant ceiling" in feedback["USER_MANAGE"]


def test_policy_diff_preview_and_high_impact_confirmation() -> None:
    diff = build_policy_change_preview({"allow": ["A"], "deny": ["B"]}, {"allow": ["A", "C"], "deny": []})
    assert diff["allow_added"] == ["C"]
    assert diff["deny_removed"] == ["B"]
    assert requires_high_impact_confirmation({"allow": ["A"], "deny": ["B"]}, {"allow": ["A", "C"], "deny": []}) is True


def test_effective_permissions_explainer_source_layers() -> None:
    layers = {
        "template": {"allow": ["USER_MANAGE"], "deny": []},
        "tenant": {"allow": [], "deny": ["USER_MANAGE"]},
        "store": {"allow": [], "deny": []},
        "user": {"allow": ["AUDIT_VIEW"], "deny": []},
    }
    explained = explain_permission(key="USER_MANAGE", layers=layers)
    assert explained.final_decision == "DENY"
    assert explained.deny_sources == ["tenant"]
    rows = format_effective_permissions(
        {
            "permissions": [{"key": "USER_MANAGE", "allowed": False}, {"key": "AUDIT_VIEW", "allowed": True}],
            "sources_trace": layers,
        },
        selected_user_id="u-1",
        selected_store_id="s-1",
    )
    assert any("blocked_by=tenant" in row for row in rows)
    assert any("user=u-1 store=s-1" in row for row in rows)
