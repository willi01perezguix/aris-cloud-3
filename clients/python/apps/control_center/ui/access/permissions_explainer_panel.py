from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionExplanation:
    key: str
    final_decision: str
    source_layers: list[str]
    deny_sources: list[str]

    def render(self) -> dict[str, object]:
        return {
            "permission": self.key,
            "final_decision": self.final_decision,
            "source_layers": self.source_layers,
            "deny_sources": self.deny_sources,
            "blocked_by_explicit_deny": bool(self.deny_sources),
        }


def explain_permission(*, key: str, layers: dict[str, dict[str, list[str]]]) -> PermissionExplanation:
    source_layers: list[str] = []
    deny_sources: list[str] = []
    final = "DENY"
    for layer in ("template", "tenant", "store", "user"):
        layer_values = layers.get(layer, {})
        if key in layer_values.get("allow", []):
            source_layers.append(f"{layer}:allow")
            final = "ALLOW"
        if key in layer_values.get("deny", []):
            source_layers.append(f"{layer}:deny")
            deny_sources.append(layer)
            final = "DENY"
    return PermissionExplanation(key=key, final_decision=final, source_layers=source_layers, deny_sources=deny_sources)
