from __future__ import annotations

from .base import BaseClient
from ..models import EffectivePermissionsResponse


class AccessControlClient(BaseClient):
    def effective_permissions(self) -> EffectivePermissionsResponse:
        data = self._request("GET", "/aris3/access-control/effective-permissions")
        return EffectivePermissionsResponse.model_validate(data)


    def effective_permissions_for_user(self, user_id: str) -> EffectivePermissionsResponse:
        data = self._request("GET", f"/aris3/access-control/effective-permissions/users/{user_id}")
        return EffectivePermissionsResponse.model_validate(data)
