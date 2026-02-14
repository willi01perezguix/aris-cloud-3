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
        if not self.state.context.selected_tenant_id:
            ErrorBanner.show("Debes seleccionar tenant antes de listar o crear stores.")
            return
        tenant_gate = PermissionGate.require_tenant_context(self.state.context)
        if not tenant_gate.allowed:
            ErrorBanner.show(tenant_gate.reason)
            return
        view_gate = PermissionGate.check(self.state.context, "stores.view")
        if not view_gate.allowed:
            ErrorBanner.show(view_gate.reason)
            return
        print(f"[loading] cargando stores para tenant={self.state.context.selected_tenant_id}...")
        try:
            stores = self.list_use_case.execute()
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
            return

        if not stores:
            print("[empty] No hay stores para el tenant seleccionado.")
        else:
            print("[ready] -- Stores --")
            for store in stores:
                print(f"{store.id} :: {store.name}")

        create_gate = PermissionGate.check(self.state.context, "stores.create")
        if not create_gate.allowed:
            print(f"[disabled] Crear store ({create_gate.reason})")
            return

        option = input("Crear store? [s/N]: ").strip().lower()
        if option != "s":
            return

        name = input("Store name: ").strip()
        if not name:
            print("[error] El nombre del store es obligatorio.")
            return

        print("[spinner] creando store...")
        try:
            result = self.create_use_case.execute(name=name)
            if result.get("status") == "already_processed":
                print("Operación ya procesada previamente.")
            else:
                print("Store creada correctamente.")
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
