from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.create_store_use_case import CreateStoreUseCase
from aris_control_2.app.application.use_cases.list_stores_use_case import ListStoresUseCase
from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.app.ui.components.error_banner import ErrorBanner
from aris_control_2.app.ui.components.permission_gate import PermissionGate


class StoresView:
    def __init__(self, list_use_case: ListStoresUseCase, create_use_case: CreateStoreUseCase, state: SessionState) -> None:
        self.list_use_case = list_use_case
        self.create_use_case = create_use_case
        self.state = state

    def render(self) -> None:
        allowed, reason = PermissionGate.require_tenant_context(self.state.context)
        if not allowed:
            ErrorBanner.show(reason)
            return
        try:
            stores = self.list_use_case.execute()
            print("-- Stores --")
            for store in stores:
                print(f"{store.id} :: {store.name}")
            option = input("Crear store? [s/N]: ").strip().lower()
            if option == "s":
                name = input("Store name: ").strip()
                self.create_use_case.execute(name=name)
                print("Store creada y listado refrescado.")
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
