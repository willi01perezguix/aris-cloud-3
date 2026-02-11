from __future__ import annotations

from apps.control_center.ui.access.permissions_explainer_panel import explain_permission


def format_effective_permissions(payload: dict, *, selected_user_id: str | None = None, selected_store_id: str | None = None) -> list[str]:
    rows: list[str] = []
    trace = payload.get("sources_trace", {})
    for perm in sorted(payload.get("permissions", []), key=lambda p: p["key"]):
        explanation = explain_permission(key=perm["key"], layers=trace)
        flag = explanation.final_decision
        context = f"user={selected_user_id or 'n/a'} store={selected_store_id or 'n/a'}"
        layers = ", ".join(explanation.source_layers) or "no_layers"
        row = f"{perm['key']}: {flag} ({layers}) [{context}]"
        if explanation.deny_sources:
            row += f" blocked_by={','.join(explanation.deny_sources)}"
        rows.append(row)
    return rows
