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
            return False, "TENANT_CONTEXT_REQUIRED"
        return False, "TENANT_SCOPE_REQUIRED"

    @classmethod
    def resolve_mutation_tenant_id(cls, context) -> tuple[str | None, str]:
        effective_tenant_id = cls.resolve_effective_tenant_id(context)
        if effective_tenant_id:
            return effective_tenant_id, ""
        if context.actor_role == cls.SUPERADMIN:
            return None, "TENANT_CONTEXT_REQUIRED"
        return None, "TENANT_SCOPE_REQUIRED"
