from __future__ import annotations


def build_policy_change_preview(before: dict[str, list[str]], after: dict[str, list[str]]) -> dict[str, list[str]]:
    before_allow = set(before.get("allow", []))
    before_deny = set(before.get("deny", []))
    after_allow = set(after.get("allow", []))
    after_deny = set(after.get("deny", []))
    return {
        "allow_added": sorted(after_allow - before_allow),
        "allow_removed": sorted(before_allow - after_allow),
        "deny_added": sorted(after_deny - before_deny),
        "deny_removed": sorted(before_deny - after_deny),
    }
