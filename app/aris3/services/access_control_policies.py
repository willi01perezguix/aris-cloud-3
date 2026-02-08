from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import StoreRolePolicy, TenantRolePolicy, UserPermissionOverride
from app.aris3.repos.access_control import AccessControlPolicyRepository
from app.aris3.repos.rbac import RoleTemplateRepository


ALLOWED_ROLE_POLICIES = {"MANAGER", "USER"}
EFFECT_ALLOW = "allow"
EFFECT_DENY = "deny"


@dataclass(frozen=True)
class PolicySnapshot:
    allow: list[str]
    deny: list[str]


class AccessControlPolicyService:
    def __init__(self, db):
        self.db = db
        self.repo = AccessControlPolicyRepository(db)
        self.role_repo = RoleTemplateRepository(db)

    def list_permission_catalog(self):
        return self.repo.list_permission_catalog()

    def get_tenant_role_policy(self, *, tenant_id: str | None, role_name: str) -> PolicySnapshot:
        allow, deny = self._partition_entries(
            self.repo.list_tenant_role_policies(tenant_id=tenant_id, role_name=role_name)
        )
        return PolicySnapshot(allow=sorted(allow), deny=sorted(deny))

    def get_store_role_policy(
        self, *, tenant_id: str, store_id: str, role_name: str
    ) -> PolicySnapshot:
        allow, deny = self._partition_entries(
            self.repo.list_store_role_policies(
                tenant_id=tenant_id,
                store_id=store_id,
                role_name=role_name,
            )
        )
        return PolicySnapshot(allow=sorted(allow), deny=sorted(deny))

    def replace_tenant_role_policy(
        self,
        *,
        tenant_id: str | None,
        role_name: str,
        allow: list[str],
        deny: list[str],
        enforce_ceiling: bool,
    ) -> tuple[PolicySnapshot, PolicySnapshot]:
        self._validate_role_policy_role(role_name)
        self._validate_allow_deny(allow, deny)
        catalog = self._catalog_codes()
        self._validate_codes(allow + deny, catalog)
        if enforce_ceiling:
            ceiling = self._tenant_admin_ceiling(tenant_id)
            requested_allow = set(allow)
            if not requested_allow.issubset(ceiling):
                raise AppError(
                    ErrorCatalog.PERMISSION_DENIED,
                    details={
                        "message": "ADMIN ceiling exceeded",
                        "disallowed": sorted(requested_allow.difference(ceiling)),
                    },
                )

        before = self.get_tenant_role_policy(tenant_id=tenant_id, role_name=role_name)
        entries = self._build_tenant_role_entries(tenant_id, role_name, allow, deny)
        self.repo.replace_tenant_role_policies(
            tenant_id=tenant_id,
            role_name=role_name,
            entries=entries,
        )
        self.db.commit()
        after = PolicySnapshot(allow=sorted(set(allow)), deny=sorted(set(deny)))
        return before, after

    def replace_store_role_policy(
        self,
        *,
        tenant_id: str,
        store_id: str,
        role_name: str,
        allow: list[str],
        deny: list[str],
        enforce_ceiling: bool,
    ) -> tuple[PolicySnapshot, PolicySnapshot]:
        self._validate_role_policy_role(role_name)
        self._validate_allow_deny(allow, deny)
        catalog = self._catalog_codes()
        self._validate_codes(allow + deny, catalog)
        if enforce_ceiling:
            ceiling = self._tenant_admin_ceiling(tenant_id)
            requested_allow = set(allow)
            if not requested_allow.issubset(ceiling):
                raise AppError(
                    ErrorCatalog.PERMISSION_DENIED,
                    details={
                        "message": "ADMIN ceiling exceeded",
                        "disallowed": sorted(requested_allow.difference(ceiling)),
                    },
                )

        before = self.get_store_role_policy(
            tenant_id=tenant_id,
            store_id=store_id,
            role_name=role_name,
        )
        entries = self._build_store_role_entries(tenant_id, store_id, role_name, allow, deny)
        self.repo.replace_store_role_policies(
            tenant_id=tenant_id,
            store_id=store_id,
            role_name=role_name,
            entries=entries,
        )
        self.db.commit()
        after = PolicySnapshot(allow=sorted(set(allow)), deny=sorted(set(deny)))
        return before, after

    def get_user_overrides(self, *, tenant_id: str, user_id: str) -> PolicySnapshot:
        allow, deny = self._partition_entries(
            self.repo.list_user_overrides(tenant_id=tenant_id, user_id=user_id)
        )
        return PolicySnapshot(allow=sorted(allow), deny=sorted(deny))

    def replace_user_overrides(
        self,
        *,
        tenant_id: str,
        user_id: str,
        allow: list[str],
        deny: list[str],
        enforce_ceiling: bool,
    ) -> tuple[PolicySnapshot, PolicySnapshot]:
        self._validate_allow_deny(allow, deny)
        catalog = self._catalog_codes()
        self._validate_codes(allow + deny, catalog)
        if enforce_ceiling:
            ceiling = self._tenant_admin_ceiling(tenant_id)
            requested_allow = set(allow)
            if not requested_allow.issubset(ceiling):
                raise AppError(
                    ErrorCatalog.PERMISSION_DENIED,
                    details={
                        "message": "ADMIN ceiling exceeded",
                        "disallowed": sorted(requested_allow.difference(ceiling)),
                    },
                )

        before = self.get_user_overrides(tenant_id=tenant_id, user_id=user_id)
        entries = self._build_user_override_entries(tenant_id, user_id, allow, deny)
        self.repo.replace_user_overrides(tenant_id=tenant_id, user_id=user_id, entries=entries)
        self.db.commit()
        after = PolicySnapshot(allow=sorted(set(allow)), deny=sorted(set(deny)))
        return before, after

    def _catalog_codes(self) -> set[str]:
        return {perm.code for perm in self.repo.list_permission_catalog()}

    def _validate_codes(self, codes: list[str], catalog: set[str]) -> None:
        invalid = sorted({code for code in codes if code not in catalog})
        if invalid:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "Unknown permission code", "invalid": invalid},
            )

    @staticmethod
    def _validate_allow_deny(allow: list[str], deny: list[str]) -> None:
        overlap = sorted(set(allow).intersection(deny))
        if overlap:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "Permission in both allow and deny", "overlap": overlap},
            )

    @staticmethod
    def _validate_role_policy_role(role_name: str) -> None:
        normalized = role_name.upper()
        if normalized not in ALLOWED_ROLE_POLICIES:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "Role policies limited to MANAGER and USER", "role": role_name},
            )

    def _tenant_admin_ceiling(self, tenant_id: str | None) -> set[str]:
        permissions = set(self.role_repo.list_permissions_for_role("ADMIN", tenant_id))
        if not permissions and tenant_id is not None:
            permissions = set(self.role_repo.list_permissions_for_role("ADMIN", None))
        return permissions

    @staticmethod
    def _partition_entries(entries) -> tuple[set[str], set[str]]:
        allow: set[str] = set()
        deny: set[str] = set()
        for entry in entries:
            effect = (entry.effect or "").lower()
            if effect == EFFECT_DENY:
                deny.add(entry.permission_code)
            else:
                allow.add(entry.permission_code)
        return allow, deny

    @staticmethod
    def _build_tenant_role_entries(
        tenant_id: str | None,
        role_name: str,
        allow: list[str],
        deny: list[str],
    ) -> list[TenantRolePolicy]:
        entries: list[TenantRolePolicy] = []
        for code in sorted(set(allow)):
            entries.append(
                TenantRolePolicy(
                    tenant_id=tenant_id,
                    role_name=role_name,
                    permission_code=code,
                    effect=EFFECT_ALLOW,
                    created_at=datetime.utcnow(),
                )
            )
        for code in sorted(set(deny)):
            entries.append(
                TenantRolePolicy(
                    tenant_id=tenant_id,
                    role_name=role_name,
                    permission_code=code,
                    effect=EFFECT_DENY,
                    created_at=datetime.utcnow(),
                )
            )
        return entries

    @staticmethod
    def _build_user_override_entries(
        tenant_id: str,
        user_id: str,
        allow: list[str],
        deny: list[str],
    ) -> list[UserPermissionOverride]:
        entries: list[UserPermissionOverride] = []
        for code in sorted(set(allow)):
            entries.append(
                UserPermissionOverride(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    permission_code=code,
                    effect=EFFECT_ALLOW,
                    created_at=datetime.utcnow(),
                )
            )
        for code in sorted(set(deny)):
            entries.append(
                UserPermissionOverride(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    permission_code=code,
                    effect=EFFECT_DENY,
                    created_at=datetime.utcnow(),
                )
            )
        return entries

    @staticmethod
    def _build_store_role_entries(
        tenant_id: str,
        store_id: str,
        role_name: str,
        allow: list[str],
        deny: list[str],
    ) -> list[StoreRolePolicy]:
        entries: list[StoreRolePolicy] = []
        for code in sorted(set(allow)):
            entries.append(
                StoreRolePolicy(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    role_name=role_name,
                    permission_code=code,
                    effect=EFFECT_ALLOW,
                    created_at=datetime.utcnow(),
                )
            )
        for code in sorted(set(deny)):
            entries.append(
                StoreRolePolicy(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    role_name=role_name,
                    permission_code=code,
                    effect=EFFECT_DENY,
                    created_at=datetime.utcnow(),
                )
            )
        return entries
