from __future__ import annotations

from dataclasses import dataclass, field

from .provider import DictFlagProvider, FeatureFlagProvider


@dataclass
class FeatureFlagStore:
    provider: FeatureFlagProvider = field(default_factory=lambda: DictFlagProvider(values={}))

    def enabled(self, key: str, *, default: bool = False) -> bool:
        state = self.provider.is_enabled(key)
        if state:
            return True
        return default if default and state is False else False

    @staticmethod
    def ensure_permission_gate(permission_allowed: bool) -> bool:
        """Flags cannot bypass permission checks. Permission remains authoritative."""
        return permission_allowed
