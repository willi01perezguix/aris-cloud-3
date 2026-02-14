class TenantContextPolicy:
    SUPERADMIN = "SUPERADMIN"

    @classmethod
    def resolve_effective_tenant_id(cls, context) -> str | None:
        if context.actor_role == cls.SUPERADMIN:
            return context.selected_tenant_id
        return context.token_tenant_id

    @classmethod
    def can_access_tenant_scoped_resources(cls, context) -> tuple[bool, str]:
        effective_tenant_id = cls.resolve_effective_tenant_id(context)
        if effective_tenant_id:
            return True, ""
        if context.actor_role == cls.SUPERADMIN:
            return False, "SUPERADMIN must select_tenant_id for stores/users"
        return False, "token_tenant_id missing"
