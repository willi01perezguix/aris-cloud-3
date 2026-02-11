from __future__ import annotations

import logging

from aris3_client_sdk import ApiSession
from collections.abc import Mapping

from aris3_client_sdk.models import EffectivePermissionsResponse, PermissionEntry

logger = logging.getLogger(__name__)


class PermissionGate:
    """Default deny permission gate with deny-overrides-allow semantics."""

    def __init__(self, entries: list[PermissionEntry | Mapping[str, object]]) -> None:
        self._decisions = self._normalize(entries)

    @staticmethod
    def _normalize(entries: list[PermissionEntry | Mapping[str, object]]) -> dict[str, bool]:
        decisions: dict[str, bool] = {}
        for raw_entry in entries:
            entry = PermissionEntry.model_validate(raw_entry)
            key = entry.key.strip()
            previous = decisions.get(key)
            if previous is False:
                continue
            decisions[key] = bool(entry.allowed)
        return decisions

    def is_allowed(self, permission_key: str) -> bool:
        return self._decisions.get(permission_key, False)

    def allows_any(self, *permission_keys: str) -> bool:
        return any(self.is_allowed(key) for key in permission_keys)

    def allowed_keys(self) -> set[str]:
        return {key for key, allowed in self._decisions.items() if allowed}


class PermissionsService:
    def __init__(self, session: ApiSession) -> None:
        self.session = session

    def load_effective_permissions(self) -> EffectivePermissionsResponse:
        logger.info("permissions_fetch_attempt")
        response = self.session.access_control_client().effective_permissions()
        logger.info(
            "permissions_fetch_success",
            extra={
                "trace_id": response.trace_id,
                "count": len(response.permissions),
            },
        )
        return response
