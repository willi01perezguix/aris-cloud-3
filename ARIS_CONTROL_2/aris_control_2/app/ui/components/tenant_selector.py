from aris_control_2.app.application.use_cases.select_tenant_use_case import SelectTenantUseCase


class TenantSelector:
    def __init__(self, use_case: SelectTenantUseCase) -> None:
        self.use_case = use_case

    def select(self) -> None:
        tenant_id = input("Tenant ID: ").strip() or None
        self.use_case.execute(tenant_id)
