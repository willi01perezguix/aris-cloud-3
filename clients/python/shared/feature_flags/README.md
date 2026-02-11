# Shared Feature Flags (Sprint 8 Day 1)

This package provides lightweight safe-rollout controls for ARIS Python clients.

## Design goals
- Provider-based lookup for flexibility (`DictFlagProvider`, `EnvFlagProvider`).
- **Default safe:** every flag is OFF unless explicitly enabled.
- Reusable by both ARIS-CORE-3 and Control Center app code.
- Flags must **never** bypass RBAC/permission checks.

## Usage
```python
from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import EnvFlagProvider

store = FeatureFlagStore(provider=EnvFlagProvider())
if store.enabled("new_stock_filters") and store.ensure_permission_gate(user_can_access_stock):
    ...
```

Environment format:
```bash
ARIS3_FLAG_NEW_STOCK_FILTERS=1
```

Accepted truthy values: `1`, `true`, `yes`, `on`.
