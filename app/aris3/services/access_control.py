from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from app.aris3.core.context import RequestContext
from app.aris3.core.security import TokenData
from app.aris3.repos.access_control import AccessControlPolicyRepository
from app.aris3.repos.rbac import RoleTemplateRepository


@dataclass(frozen=True)
class PermissionDecision:
    key: str
    allowed: bool
    source: str


@dataclass(frozen=True)
class PermissionTrace:
    template_allow: set[str]
    tenant_allow: set[str]
    tenant_deny: set[str]
    store_allow: set[str]
    store_deny: set[str]
    user_allow: set[str]
    user_deny: set[str]


class AccessControlService:
    def __init__(
        self,
        db,
        cache: dict | None = None,
        deny_resolvers: Iterable[Callable[[RequestContext], Iterable[str]]] | None = None,
    ):
        self.repo = RoleTemplateRepository(db)
        self.policy_repo = AccessControlPolicyRepository(db)
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

        role_name, tenant_id, store_id = self._resolve_role_scope(context, token_data)
        if not role_name:
            return PermissionDecision(key=normalized_key, allowed=False, source="default_deny")

        base_allowed = self._get_allowed_permissions(role_name, tenant_id)
        tenant_allow, tenant_deny = self._get_tenant_role_policy(tenant_id, role_name)
        store_allow, store_deny = self._get_store_role_policy(tenant_id, store_id, role_name)
        user_allow, user_deny = self._get_user_overrides(tenant_id, context.user_id)
        deny_permissions = self._get_denied_permissions(context, token_data)
        if normalized_key in deny_permissions:
            return PermissionDecision(key=normalized_key, allowed=False, source="explicit_deny")

        if normalized_key in user_deny:
            return PermissionDecision(key=normalized_key, allowed=False, source="user_override_deny")
        if normalized_key in store_deny:
            return PermissionDecision(key=normalized_key, allowed=False, source="store_policy_deny")
        if normalized_key in tenant_deny:
            return PermissionDecision(key=normalized_key, allowed=False, source="tenant_policy_deny")
        if normalized_key in user_allow:
            return PermissionDecision(key=normalized_key, allowed=True, source="user_override_allow")
        if normalized_key in store_allow:
            return PermissionDecision(key=normalized_key, allowed=True, source="store_policy_allow")
        if normalized_key in tenant_allow:
            return PermissionDecision(key=normalized_key, allowed=True, source="tenant_policy_allow")
        if normalized_key in base_allowed:
            return PermissionDecision(key=normalized_key, allowed=True, source="role_template")

        return PermissionDecision(key=normalized_key, allowed=False, source="default_deny")

    def build_effective_permissions(
        self,
        context: RequestContext,
        token_data: TokenData | None = None,
    ) -> list[PermissionDecision]:
        decisions, _trace = self.build_effective_permissions_with_trace(context, token_data)
        return decisions

    def build_effective_permissions_with_trace(
        self,
        context: RequestContext,
        token_data: TokenData | None = None,
    ) -> tuple[list[PermissionDecision], PermissionTrace]:
        role_name, tenant_id, store_id = self._resolve_role_scope(context, token_data)
        catalog = sorted(self._get_catalog_permissions())
        deny_permissions = self._get_denied_permissions(context, token_data)
        base_allowed = self._get_allowed_permissions(role_name, tenant_id) if role_name else set()
        tenant_allow, tenant_deny = self._get_tenant_role_policy(tenant_id, role_name) if role_name else (set(), set())
        store_allow, store_deny = (
            self._get_store_role_policy(tenant_id, store_id, role_name) if role_name else (set(), set())
        )
        user_allow, user_deny = self._get_user_overrides(tenant_id, context.user_id)

        decisions = self._build_decisions(
            catalog=catalog,
            deny_permissions=deny_permissions,
            base_allowed=base_allowed,
            tenant_allow=tenant_allow,
            tenant_deny=tenant_deny,
            store_allow=store_allow,
            store_deny=store_deny,
            user_allow=user_allow,
            user_deny=user_deny,
        )
        trace = PermissionTrace(
            template_allow=base_allowed,
            tenant_allow=tenant_allow,
            tenant_deny=tenant_deny,
            store_allow=store_allow,
            store_deny=store_deny,
            user_allow=user_allow,
            user_deny=user_deny,
        )
        return decisions, trace

    @staticmethod
    def _build_decisions(
        *,
        catalog: list[str],
        deny_permissions: set[str],
        base_allowed: set[str],
        tenant_allow: set[str],
        tenant_deny: set[str],
        store_allow: set[str],
        store_deny: set[str],
        user_allow: set[str],
        user_deny: set[str],
    ) -> list[PermissionDecision]:
        decisions: list[PermissionDecision] = []
        for key in catalog:
            # Evaluation order (deterministic): template -> tenant policy -> store policy -> user override,
            # with DENY precedence at every level.
            if key in deny_permissions:
                decisions.append(PermissionDecision(key=key, allowed=False, source="explicit_deny"))
                continue
            if key in user_deny:
                decisions.append(PermissionDecision(key=key, allowed=False, source="user_override_deny"))
                continue
            if key in store_deny:
                decisions.append(PermissionDecision(key=key, allowed=False, source="store_policy_deny"))
                continue
            if key in tenant_deny:
                decisions.append(PermissionDecision(key=key, allowed=False, source="tenant_policy_deny"))
                continue
            if key in user_allow:
                decisions.append(PermissionDecision(key=key, allowed=True, source="user_override_allow"))
                continue
            if key in store_allow:
                decisions.append(PermissionDecision(key=key, allowed=True, source="store_policy_allow"))
                continue
            if key in tenant_allow:
                decisions.append(PermissionDecision(key=key, allowed=True, source="tenant_policy_allow"))
                continue
            if key in base_allowed:
                decisions.append(PermissionDecision(key=key, allowed=True, source="role_template"))
                continue
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

        permissions = set(self.repo.list_permissions_for_role(role_name, tenant_id))
        if not permissions and tenant_id is not None:
            permissions = set(self.repo.list_permissions_for_role(role_name, None))

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

    def _get_tenant_role_policy(self, tenant_id: str | None, role_name: str | None) -> tuple[set[str], set[str]]:
        if not role_name:
            return set(), set()
        cache_key = f"tenant_policy:{tenant_id}:{role_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        entries = self.policy_repo.list_tenant_role_policies(tenant_id=tenant_id, role_name=role_name)
        allow: set[str] = set()
        deny: set[str] = set()
        for entry in entries:
            effect = (entry.effect or "").lower()
            if effect == "deny":
                deny.add(entry.permission_code)
            else:
                allow.add(entry.permission_code)
        self.cache[cache_key] = (allow, deny)
        return allow, deny

    def _get_user_overrides(self, tenant_id: str | None, user_id: str | None) -> tuple[set[str], set[str]]:
        if not tenant_id or not user_id:
            return set(), set()
        cache_key = f"user_overrides:{tenant_id}:{user_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        entries = self.policy_repo.list_user_overrides(tenant_id=tenant_id, user_id=user_id)
        allow: set[str] = set()
        deny: set[str] = set()
        for entry in entries:
            effect = (entry.effect or "").lower()
            if effect == "deny":
                deny.add(entry.permission_code)
            else:
                allow.add(entry.permission_code)
        self.cache[cache_key] = (allow, deny)
        return allow, deny

    def _get_store_role_policy(
        self,
        tenant_id: str | None,
        store_id: str | None,
        role_name: str | None,
    ) -> tuple[set[str], set[str]]:
        if not tenant_id or not store_id or not role_name:
            return set(), set()
        cache_key = f"store_policy:{tenant_id}:{store_id}:{role_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        entries = self.policy_repo.list_store_role_policies(
            tenant_id=tenant_id,
            store_id=store_id,
            role_name=role_name,
        )
        allow: set[str] = set()
        deny: set[str] = set()
        for entry in entries:
            effect = (entry.effect or "").lower()
            if effect == "deny":
                deny.add(entry.permission_code)
            else:
                allow.add(entry.permission_code)
        self.cache[cache_key] = (allow, deny)
        return allow, deny

    @staticmethod
    def _resolve_role_scope(
        context: RequestContext,
        token_data: TokenData | None,
    ) -> tuple[str | None, str | None, str | None]:
        role = (context.role or (token_data.role if token_data else "")).upper() or None
        tenant_id = context.tenant_id or (token_data.tenant_id if token_data else None)
        store_id = context.store_id or (token_data.store_id if token_data else None)
        return role, tenant_id, store_id
