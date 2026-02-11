from __future__ import annotations


def format_effective_permissions(payload: dict) -> list[str]:
    rows: list[str] = []
    for perm in sorted(payload.get("permissions", []), key=lambda p: p["key"]):
        flag = "ALLOW" if perm.get("allowed") else "DENY"
        rows.append(f"{perm['key']}: {flag} ({perm.get('source', 'unknown')})")
    return rows
