from __future__ import annotations

from apps.control_center.services.access_control_service import blocked_admin_grants
from apps.control_center.ui.access.policy_diff_panel import build_policy_change_preview

PRECEDENCE_LAYERS = ("global template", "tenant policy", "store policy", "user override")


def resolve_precedence(allow: set[str], deny: set[str]) -> dict[str, bool]:
    result = {perm: True for perm in allow}
    for denied in deny:
        result[denied] = False
    return result


def precedence_summary() -> str:
    return " -> ".join(PRECEDENCE_LAYERS)


def deny_warning(has_deny_rules: bool) -> str | None:
    if has_deny_rules:
        return "Explicit DENY always overrides ALLOW across all policy layers."
    return None


def block_for_admin_ceiling(actor_allowed: set[str], requested_allow: set[str]) -> dict[str, str]:
    blocked = blocked_admin_grants(actor_allowed, requested_allow)
    return {perm: "Grant exceeds ADMIN tenant ceiling for current actor" for perm in blocked}


def requires_high_impact_confirmation(before: dict[str, list[str]], after: dict[str, list[str]]) -> bool:
    preview = build_policy_change_preview(before, after)
    return bool(preview["allow_added"] or preview["deny_removed"])
