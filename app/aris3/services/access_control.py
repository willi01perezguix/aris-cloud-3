from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from app.aris3.core.context import RequestContext
from app.aris3.core.security import TokenData
from app.aris3.repos.rbac import RoleTemplateRepository


@dataclass(frozen=True)
class PermissionDecision:
    key: str
    allowed: bool
    source: str


class AccessControlService:
    def __init__(
        self,
        db,
        cache: dict | None = None,
        deny_resolvers: Iterable[Callable[[RequestContext], Iterable[str]]] | None = None,
    ):
        self.repo = RoleTemplateRepository(db)
        self.cache = cache if cache is not None else {}
        self.deny_resolvers = list(deny_resolvers or [])

    def evaluate_permission(
        self,
        permission_key: str,
        context: RequestContext,
        token_data: TokenData | None = None,
    ) -> PermissionDecision:
        normalized_key = permission_key.strip()
        catalog = self._get_catalog_permissions()
        if normalized_key not in catalog:
            return PermissionDecision(key=normalized_key, allowed=False, source="unknown_permission")

        role_name, tenant_id = self._resolve_role_scope(context, token_data)
        if not role_name:
            return PermissionDecision(key=normalized_key, allowed=False, source="default_deny")

        deny_permissions = self._get_denied_permissions(context, token_data)
        if normalized_key in deny_permissions:
            return PermissionDecision(key=normalized_key, allowed=False, source="explicit_deny")

        allowed_permissions = self._get_allowed_permissions(role_name, tenant_id)
        if normalized_key in allowed_permissions:
            return PermissionDecision(key=normalized_key, allowed=True, source="role_template")

        return PermissionDecision(key=normalized_key, allowed=False, source="default_deny")

    def build_effective_permissions(
        self,
        context: RequestContext,
        token_data: TokenData | None = None,
    ) -> list[PermissionDecision]:
        role_name, tenant_id = self._resolve_role_scope(context, token_data)
        catalog = sorted(self._get_catalog_permissions())
        deny_permissions = self._get_denied_permissions(context, token_data)
        allowed_permissions = self._get_allowed_permissions(role_name, tenant_id) if role_name else set()

        decisions: list[PermissionDecision] = []
        for key in catalog:
            if key in deny_permissions:
                decisions.append(PermissionDecision(key=key, allowed=False, source="explicit_deny"))
            elif key in allowed_permissions:
                decisions.append(PermissionDecision(key=key, allowed=True, source="role_template"))
            else:
                decisions.append(PermissionDecision(key=key, allowed=False, source="default_deny"))
        return decisions

    def _get_catalog_permissions(self) -> set[str]:
        cache_key = "catalog_permissions"
        if cache_key in self.cache:
            return self.cache[cache_key]
        permissions = {perm.code for perm in self.repo.list_permission_catalog()}
        self.cache[cache_key] = permissions
        return permissions

    def _get_allowed_permissions(self, role_name: str, tenant_id: str | None) -> set[str]:
        cache_key = f"role_permissions:{tenant_id}:{role_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        role_template = self.repo.get_role_template(role_name, tenant_id)
        if role_template is None and tenant_id is not None:
            role_template = self.repo.get_role_template(role_name, None)
        if role_template is None:
            permissions: set[str] = set()
        else:
            permissions = set(self.repo.list_permissions_for_role_template(role_template.id))

        self.cache[cache_key] = permissions
        return permissions

    def _get_denied_permissions(
        self,
        context: RequestContext,
        token_data: TokenData | None,
    ) -> set[str]:
        if not self.deny_resolvers:
            return set()
        denied: set[str] = set()
        for resolver in self.deny_resolvers:
            denied.update(resolver(context))
        return denied

    @staticmethod
    def _resolve_role_scope(
        context: RequestContext,
        token_data: TokenData | None,
    ) -> tuple[str | None, str | None]:
        role = (context.role or (token_data.role if token_data else "")).upper() or None
        tenant_id = context.tenant_id or (token_data.tenant_id if token_data else None)
        return role, tenant_id
