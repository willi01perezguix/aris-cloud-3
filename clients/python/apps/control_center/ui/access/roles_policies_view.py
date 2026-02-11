from __future__ import annotations

from apps.control_center.services.access_control_service import blocked_admin_grants


def resolve_precedence(allow: set[str], deny: set[str]) -> dict[str, bool]:
    result = {perm: True for perm in allow}
    for denied in deny:
        result[denied] = False
    return result


def block_for_admin_ceiling(actor_allowed: set[str], requested_allow: set[str]) -> dict[str, str]:
    blocked = blocked_admin_grants(actor_allowed, requested_allow)
    return {perm: "Grant exceeds ADMIN tenant ceiling" for perm in blocked}
