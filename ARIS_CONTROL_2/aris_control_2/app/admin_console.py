from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.idempotency import generate_idempotency_key
from clients.aris3_client_sdk.stores_client import StoresClient
from clients.aris3_client_sdk.tenants_client import TenantsClient
from clients.aris3_client_sdk.users_client import UsersClient

from aris_control_2.app.error_presenter import build_error_payload, print_error_banner
from aris_control_2.app.export.csv_exporter import export_current_view
from aris_control_2.app.listing_cache import ListingCache
from aris_control_2.app.operational_support import OperationalSupportCenter
from aris_control_2.app.state import SessionState
from aris_control_2.app.tenant_context import TenantContextError, is_superadmin, resolve_operational_tenant_id
from aris_control_2.app.ui.filters import clean_filters, debounce_text, prompt_optional
from aris_control_2.app.ui.listing_view import ColumnDef, hydrate_view_state, serialize_view_state, sort_rows
from aris_control_2.app.ui.pagination import PaginationState, goto_page, next_page, prev_page
from aris_control_2.app.ui.table_printer import print_table


class AdminConsole:
    def __init__(
        self,
        tenants: TenantsClient,
        stores: StoresClient,
        users: UsersClient,
        support_center: OperationalSupportCenter | None = None,
        on_context_updated: Callable[[], None] | None = None,
        on_open_diagnostics: Callable[[], None] | None = None,
        on_export_support: Callable[[], None] | None = None,
    ) -> None:
        self.tenants = tenants
        self.stores = stores
        self.users = users
        self.support_center = support_center or OperationalSupportCenter.load()
        self._on_context_updated = on_context_updated
        self._on_open_diagnostics = on_open_diagnostics
        self._on_export_support = on_export_support
        self._listing_cache = ListingCache(ttl_seconds=20)
        self._last_refresh_at_by_module: dict[str, float] = {}
        self._auto_refresh_by_module: dict[str, bool] = {}
        self._consecutive_errors_by_module: dict[str, int] = {}
        self._last_load_duration_ms_by_module: dict[str, int] = {}
        self._health_status_by_module: dict[str, str] = {}

    def run(self, session: SessionState) -> None:
        session.current_module = "admin_core"
        while True:
            print("\nAdmin Core")
            print("Accesos rápidos: t=Tenants, s=Stores, u=Users")
            print(
                "Contexto activo: "
                f"tenant={session.selected_tenant_id or session.effective_tenant_id or 'N/A'} "
                f"role={session.role or 'N/A'}"
            )
            print("1. Seleccionar tenant (solo SUPERADMIN)")
            print("2. Listar tenants")
            print("3. Crear tenant (SUPERADMIN)")
            print("4. Listar stores (tenant operativo)")
            print("5. Crear store (tenant operativo)")
            print("6. Listar users (tenant operativo)")
            print("7. Crear user (tenant operativo + store válido)")
            print("8. Acción sobre user (set_role / set_status / reset_password)")
            print("9. Volver")
            option = input("Selecciona una opción: ").strip().lower()

            try:
                if option == "1":
                    self._select_tenant(session)
                elif option == "2":
                    self._list_tenants(session)
                elif option == "3":
                    self._create_tenant(session)
                elif option == "4":
                    self._list_stores(session)
                elif option == "5":
                    self._create_store(session)
                elif option == "6":
                    self._list_users(session)
                elif option == "7":
                    self._create_user(session)
                elif option == "8":
                    self._user_action(session)
                elif option == "9":
                    session.current_module = "menu_principal"
                    return
                elif option == "t":
                    self._list_tenants(session)
                elif option == "s":
                    self._list_stores(session)
                elif option == "u":
                    self._list_users(session)
                else:
                    print("Opción no válida.")
            except TenantContextError as error:
                print(f"Guardrail: {error}")
            except ApiError as error:
                payload = build_error_payload(error)
                self.support_center.record_incident(module=session.current_module, payload=payload)
                self.support_center.record_operation(module=session.current_module, screen=session.current_module, action="admin_operation", result="error", latency_ms=0, trace_id=payload.get("trace_id"), code=payload.get("code"), message=payload.get("message"))
                self._print_action_result_panel(operation=session.current_module, status="error", code=payload.get("code"), message=payload.get("message"), trace_id=payload.get("trace_id"))
                print_error_banner(payload)

    def _select_tenant(self, session: SessionState) -> None:
        if not is_superadmin(session.role):
            print("Solo SUPERADMIN puede seleccionar tenant. Se usa tenant efectivo del actor.")
            return
        tenant_id = input("tenant_id a seleccionar: ").strip()
        if not tenant_id:
            self._print_validation_error("tenant_id es requerido.")
            return
        self._set_selected_tenant(session, tenant_id)
        print(f"Tenant seleccionado: {tenant_id}")

    def _list_tenants(self, session: SessionState) -> None:
        self._require_superadmin(session)
        self._prompt_filters(session, "tenants", ["q"])
        self._run_listing_loop(
            module="tenants",
            session=session,
            fetch_page=lambda page, page_size: self.tenants.list_tenants(
                session.access_token or "",
                page=page,
                page_size=page_size,
                q=session.filters_by_module.get("tenants", {}).get("q"),
            ),
            columns=[ColumnDef("id", "id"), ColumnDef("code", "code"), ColumnDef("name", "name"), ColumnDef("status", "status")],
            filter_keys=["q"],
        )

    def _create_tenant(self, session: SessionState) -> None:
        self._require_superadmin(session)
        code = input("code: ").strip()
        name = input("name: ").strip()
        if not code or not name:
            self._print_validation_error("code y name son requeridos.")
            return
        payload = {"code": code, "name": name}
        result = self.tenants.create_tenant(session.access_token or "", payload, generate_idempotency_key())
        self._invalidate_read_cache("tenants")
        print(f"Tenant creado: {result}")

    def _list_stores(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        self._prompt_filters(session, "stores", ["q", "status"])
        self._run_listing_loop(
            module="stores",
            session=session,
            fetch_page=lambda page, page_size: self.stores.list_stores(
                session.access_token or "",
                tenant_id,
                page=page,
                page_size=page_size,
                q=session.filters_by_module.get("stores", {}).get("q"),
                status=session.filters_by_module.get("stores", {}).get("status"),
            ),
            columns=[ColumnDef("id", "id"), ColumnDef("code", "code"), ColumnDef("name", "name"), ColumnDef("status", "status"), ColumnDef("tenant_id", "tenant_id")],
            filter_keys=["q", "status"],
        )

    def _create_store(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        code = input("code: ").strip()
        name = input("name: ").strip()
        if not code or not name:
            self._print_validation_error("code y name son requeridos.")
            return
        payload = {"tenant_id": tenant_id, "code": code, "name": name}
        started = time.monotonic()
        created = self.stores.create_store(session.access_token or "", payload, generate_idempotency_key())
        latency_ms = int((time.monotonic() - started) * 1000)
        self.support_center.record_operation(module="stores", screen="create_store", action="create_store", result="success", latency_ms=latency_ms, code="OK", message="store creada")
        self._print_action_result_panel(operation="create_store", status="success", code="OK", message="Store creada", trace_id=None)
        self._invalidate_read_cache("stores")
        print(f"Store creada: {created}")

    def _list_users(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        self._prompt_filters(session, "users", ["q", "role", "status", "store_id"])

        if not self._ensure_users_store_filter_is_valid(session, tenant_id):
            self._persist_context()

        def _fetch(page: int, page_size: int) -> dict[str, Any]:
            current_filters = session.filters_by_module.get("users", {})
            listing = self.users.list_users(
                session.access_token or "",
                tenant_id,
                page=page,
                page_size=page_size,
                q=current_filters.get("q"),
                role=current_filters.get("role"),
                status=current_filters.get("status"),
            )
            store_id = current_filters.get("store_id")
            rows = listing.get("rows", [])
            if store_id:
                rows = [row for row in rows if str(row.get("store_id") or "") == store_id]
            listing["rows"] = [
                {
                    **row,
                    "username_or_email": row.get("username") or row.get("email"),
                }
                for row in rows
            ]
            return listing

        self._run_listing_loop(
            module="users",
            session=session,
            fetch_page=_fetch,
            columns=[
                ColumnDef("id", "id"),
                ColumnDef("username_or_email", "username_or_email"),
                ColumnDef("role", "role"),
                ColumnDef("status", "status"),
                ColumnDef("store_id", "store_id"),
                ColumnDef("tenant_id", "tenant_id"),
            ],
            filter_keys=["q", "role", "status", "store_id"],
        )

    def _run_listing_loop(
        self,
        module: str,
        session: SessionState,
        fetch_page: Callable[[int, int], dict[str, Any]],
        columns: list[ColumnDef],
        filter_keys: list[str],
    ) -> None:
        session.current_module = module
        page_state = self._load_pagination_state(session, module)
        view_state = hydrate_view_state(session.listing_view_by_module.get(module), columns)

        while True:
            active_tenant = session.selected_tenant_id or session.effective_tenant_id or "N/A"
            print(
                f"[loading] Cargando {module} tenant={active_tenant} "
                f"page={page_state.page} page_size={page_state.page_size}..."
            )
            try:
                listing = self._fetch_listing_with_cache(
                    module=module,
                    session=session,
                    page=page_state.page,
                    page_size=page_state.page_size,
                    fetch_page=fetch_page,
                    force_refresh=False,
                )
            except Exception as error:  # noqa: BLE001
                payload = build_error_payload(error)
                print(f"[error] {module.upper()}: no se pudo cargar el listado actual.")
                print_error_banner(payload)
                self.support_center.record_incident(module=module, payload=payload)
                errors = self._consecutive_errors_by_module.get(module, 0) + 1
                self._consecutive_errors_by_module[module] = errors
                if errors >= 2:
                    print("[ALERTA] Errores consecutivos detectados en esta vista.")
                print("Acciones: t=reintentar, f=filtros, c=limpiar filtros, d=diagnóstico, e=exportar soporte, b=back")
                command = input("cmd error: ").strip().lower()
                if command == "t":
                    continue
                if command == "f":
                    self._update_filters_for_module(session, module, filter_keys)
                    continue
                if command == "c":
                    self._clear_filters_for_module(session, module)
                    continue
                if command == "d" and self._on_open_diagnostics:
                    self._on_open_diagnostics()
                    continue
                if command == "e" and self._on_export_support:
                    self._on_export_support()
                    continue
                if command == "b":
                    session.current_module = "admin_core"
                    return
                continue

            self._consecutive_errors_by_module[module] = 0
            self.support_center.mark_module_mitigated(module)

            rows = sort_rows(listing.get("rows", []), view_state)
            page_state.page = int(listing.get("page") or page_state.page)
            page_state.page_size = int(listing.get("page_size") or page_state.page_size)
            self._save_pagination_state(session, module, page_state)

            visible_columns = [column for column in columns if column.key in set(view_state.visible_columns)]
            if not visible_columns:
                visible_columns = columns
            table_columns = [(column.key, column.label) for column in visible_columns]

            _print_context_header(
                session,
                listing,
                self._last_refresh_at_by_module.get(module),
                self._last_load_duration_ms_by_module.get(module),
                self._health_status_by_module.get(module, "OK"),
            )
            if rows:
                print_table(module.upper(), rows, table_columns)
            else:
                print(f"[empty] {module.upper()}: {self._contextual_empty_message(session, module)}")
            auto_refresh_label = "ON" if self._auto_refresh_by_module.get(module, False) else "OFF"
            export_allowed = self._can_export_module(session, module)
            export_label = "x=export csv, " if export_allowed else ""
            print(
                "\nComandos: n=next, p=prev, g=goto, z=page_size, r=actualizar, "
                f"a=auto-refresh ({auto_refresh_label}), s=ordenar, v=configurar columnas, d=duplicar filtros relacionados, "
                f"f=filtros, c=limpiar filtros, w=restablecer vista, q=atajos, y=copiar id, {export_label}b=back"
            )
            command = input("cmd: ").strip().lower()

            if command == "n":
                next_page(page_state, listing.get("has_next"))
                self._save_pagination_state(session, module, page_state)
            elif command == "p":
                prev_page(page_state)
                self._save_pagination_state(session, module, page_state)
            elif command == "g":
                requested = input("page: ").strip()
                if requested.isdigit():
                    goto_page(page_state, int(requested))
                    self._save_pagination_state(session, module, page_state)
            elif command == "z":
                requested_size = input("page_size: ").strip()
                if requested_size.isdigit() and int(requested_size) > 0:
                    page_state.page_size = int(requested_size)
                    page_state.page = 1
                    self._save_pagination_state(session, module, page_state)
            elif command == "r":
                print("[refresh] Recargando listado y preservando tenant/filtros/paginación activos...")
                self._fetch_listing_with_cache(
                    module=module,
                    session=session,
                    page=page_state.page,
                    page_size=page_state.page_size,
                    fetch_page=fetch_page,
                    force_refresh=True,
                )
                continue
            elif command == "a":
                enabled = not self._auto_refresh_by_module.get(module, False)
                self._auto_refresh_by_module[module] = enabled
                print(f"[refresh] Auto-refresh {'activado' if enabled else 'desactivado'} (solo lectura).")
            elif command == "s":
                self._configure_sort(module, view_state, columns)
                self._save_listing_view_state(session, module, view_state)
            elif command == "v":
                self._configure_visible_columns(module, view_state, columns)
                self._save_listing_view_state(session, module, view_state)
            elif command == "d":
                self._duplicate_related_filters(session, module)
            elif command == "f":
                self._update_filters_for_module(session, module, filter_keys)
                page_state.page = 1
                self._save_pagination_state(session, module, page_state)
            elif command == "c":
                self._clear_filters_for_module(session, module)
                page_state.page = 1
                self._save_pagination_state(session, module, page_state)
            elif command == "w":
                view_state = hydrate_view_state(None, columns)
                self._save_listing_view_state(session, module, view_state)
                print("[view] Vista restablecida al estado por defecto.")
            elif command == "x" and export_allowed:
                exported = export_current_view(
                    module=module,
                    rows=rows,
                    headers=[column.label for column in visible_columns],
                    tenant_id=session.selected_tenant_id or session.effective_tenant_id,
                    filters=session.filters_by_module.get(module, {}),
                )
                print(f"CSV exportado: {exported}")
            elif command == "q":
                if self._handle_navigation_shortcut(session, module):
                    return
            elif command == "y":
                self._copy_operational_id(session, module)
            elif command == "b":
                session.current_module = "admin_core"
                return

            if self._auto_refresh_by_module.get(module, False):
                print("[refresh] Reintentando actualización no intrusiva...")
                try:
                    self._fetch_listing_with_cache(
                        module=module,
                        session=session,
                        page=page_state.page,
                        page_size=page_state.page_size,
                        fetch_page=fetch_page,
                        force_refresh=True,
                    )
                except Exception:  # noqa: BLE001
                    pass

    def _create_user(self, session: SessionState) -> None:
        tenant_id = self._resolve_tenant(session)
        username = input("username: ").strip()
        email = input("email: ").strip()
        role = input("role: ").strip().upper()
        password = input("password: ").strip()
        store_id = input("store_id: ").strip()
        if not username or not email or not role or not password or not store_id:
            self._print_validation_error("username, email, role, password y store_id son requeridos.")
            return

        stores_listing = self.stores.list_stores(session.access_token or "", tenant_id, page=1, page_size=500)
        stores_rows = stores_listing.get("rows", stores_listing if isinstance(stores_listing, list) else [])
        store = next((item for item in stores_rows if str(item.get("id")) == store_id), None)
        if not store:
            self._print_validation_error("store_id no pertenece al tenant operativo. Operación cancelada.", code="TENANT_STORE_GUARDRAIL")
            return
        if str(store.get("tenant_id") or "") and str(store.get("tenant_id")) != tenant_id:
            self._print_validation_error("mismatch tenant/store detectado. Operación cancelada.", code="TENANT_STORE_GUARDRAIL")
            return

        payload = {
            "tenant_id": tenant_id,
            "store_id": store_id,
            "username": username,
            "email": email,
            "role": role,
            "password": password,
        }
        started = time.monotonic()
        created = self.users.create_user(session.access_token or "", payload, generate_idempotency_key())
        latency_ms = int((time.monotonic() - started) * 1000)
        self.support_center.record_operation(module="users", screen="create_user", action="create_user", result="success", latency_ms=latency_ms, code="OK", message="user creado")
        self._print_action_result_panel(operation="create_user", status="success", code="OK", message="User creado", trace_id=None)
        self._invalidate_read_cache("users")
        print(f"User creado: {created}")

    def _user_action(self, session: SessionState) -> None:
        self._resolve_tenant(session)
        user_id = input("user_id: ").strip()
        action = input("action [set_role|set_status|reset_password]: ").strip()
        if not user_id:
            self._print_validation_error("user_id es requerido para ejecutar acciones.")
            return
        payload = self._build_user_action_payload(action)
        if payload is None:
            self._print_validation_error("acción inválida o payload incompleto para user_action.")
            return
        started = time.monotonic()
        result = self.users.user_action(
            session.access_token or "",
            user_id=user_id,
            action=action,
            action_payload=payload,
            idempotency_key=generate_idempotency_key(),
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        self.support_center.record_operation(module="users", screen="user_action", action=action, result="success", latency_ms=latency_ms, code="OK", message="acción aplicada")
        self._print_action_result_panel(operation=f"user_action:{action}", status="success", code="OK", message="Acción aplicada", trace_id=None)
        self._invalidate_read_cache("users")
        print(f"Acción aplicada: {result}")


    def _print_action_result_panel(self, *, operation: str, status: str, code: str | None, message: str | None, trace_id: str | None) -> None:
        print("\n[RESULTADO OPERACIÓN]")
        print(f"  operación: {operation}")
        print(f"  estado_final: {status}")
        print(f"  code: {code or 'N/A'}")
        print(f"  message: {message or 'N/A'}")
        print(f"  trace_id: {trace_id or 'N/A'}")

    def _build_user_action_payload(self, action: str) -> dict | None:
        if action == "set_role":
            role = input("new role: ").strip().upper()
            return {"role": role} if role else None
        if action == "set_status":
            status = input("new status: ").strip().upper()
            return {"status": status} if status else None
        if action == "reset_password":
            new_password = input("new_password: ").strip()
            return {"new_password": new_password} if new_password else None
        return None

    def _resolve_tenant(self, session: SessionState) -> str:
        return resolve_operational_tenant_id(session.role, session.effective_tenant_id, session.selected_tenant_id)

    def _set_selected_tenant(self, session: SessionState, tenant_id: str) -> None:
        previous = session.selected_tenant_id
        session.selected_tenant_id = tenant_id
        if previous and previous != tenant_id:
            session.reset_module_state("stores")
            session.reset_module_state("users")
            self._invalidate_read_cache("stores")
            self._invalidate_read_cache("users")
            users_filters = session.filters_by_module.get("users", {}).copy()
            users_filters.pop("store_id", None)
            session.filters_by_module["users"] = clean_filters(users_filters)
            print("[context] Tenant cambiado: store_id de users reiniciado para evitar mezcla de contexto.")
        self._persist_context()

    def _ensure_users_store_filter_is_valid(self, session: SessionState, tenant_id: str) -> bool:
        users_filters = session.filters_by_module.get("users", {})
        store_id = users_filters.get("store_id")
        if not store_id:
            return True
        stores_listing = self.stores.list_stores(session.access_token or "", tenant_id, page=1, page_size=500)
        stores_rows = stores_listing.get("rows", stores_listing if isinstance(stores_listing, list) else [])
        store = next((item for item in stores_rows if str(item.get("id") or "") == store_id), None)
        if store and str(store.get("tenant_id") or tenant_id) == tenant_id:
            return True
        users_filters.pop("store_id", None)
        session.filters_by_module["users"] = clean_filters(users_filters)
        print("[context] store_id inválido para tenant activo. Filtro limpiado.")
        return False

    def _handle_navigation_shortcut(self, session: SessionState, module: str) -> bool:
        if module == "tenants":
            tenant_id = input("tenant_id para abrir stores [vacío=tenant actual]: ").strip()
            if not tenant_id:
                try:
                    tenant_id = self._resolve_tenant(session)
                except TenantContextError:
                    self._print_validation_error("Selecciona tenant para abrir stores.", code="TENANT_CONTEXT_REQUIRED")
                    return False
            self._set_selected_tenant(session, tenant_id)
            print(f"[quick-nav] Tenant activo: {tenant_id}. Abriendo stores...")
            self._list_stores(session)
            return True
        if module == "stores":
            store_id = input("store_id para filtrar users [vacío=sin filtro]: ").strip()
            users_filters = session.filters_by_module.get("users", {}).copy()
            if store_id:
                users_filters["store_id"] = store_id
            else:
                users_filters.pop("store_id", None)
            session.filters_by_module["users"] = clean_filters(users_filters)
            self._persist_context()
            print("[quick-nav] Contexto de users actualizado desde stores. Abriendo users...")
            self._list_users(session)
            return True
        print(f"[quick-nav] {module} no tiene atajos relacionados.")
        return False

    def _copy_operational_id(self, session: SessionState, module: str) -> None:
        if module == "tenants":
            tenant_id = session.selected_tenant_id or session.effective_tenant_id
            if not tenant_id:
                print("[copy] No hay tenant activo para copiar.")
                return
            print(f"[copy] tenant_id={tenant_id}")
            return
        if module == "stores":
            store_id = session.filters_by_module.get("users", {}).get("store_id") or input("store_id a copiar: ").strip()
            if not store_id:
                print("[copy] store_id vacío.")
                return
            print(f"[copy] store_id={store_id}")
            return
        print(f"[copy] Usa y en tenants/stores para copiar IDs operativos.")

    def _contextual_empty_message(self, session: SessionState, module: str) -> str:
        tenant = session.selected_tenant_id or session.effective_tenant_id
        if module == "stores" and not tenant:
            return "Debes seleccionar tenant para ver stores. Acción rápida: q para navegar desde tenants."
        if module == "users" and not tenant:
            return "Debes seleccionar tenant para ver users. Acción rápida: vuelve a tenants y fija contexto."
        if module == "users" and session.filters_by_module.get("users", {}).get("store_id"):
            return "No hay users para la store filtrada. Acción rápida: c=limpiar filtros o q=atajo desde stores."
        return "sin resultados para los filtros actuales. Ajusta filtros, limpia (c) o recarga (r)."

    def _require_superadmin(self, session: SessionState) -> None:
        if not is_superadmin(session.role):
            raise TenantContextError("Operación permitida solo para SUPERADMIN.")

    def _prompt_filters(self, session: SessionState, module: str, keys: list[str]) -> dict[str, str]:
        current = session.filters_by_module.get(module, {})
        prompted = {key: prompt_optional(f"{key} [{current.get(key, '')}]") or current.get(key, "") for key in keys}
        if "q" in prompted:
            prompted["q"] = debounce_text(prompted.get("q", ""), wait_ms=350)
        filters = clean_filters(prompted)
        session.filters_by_module[module] = filters
        self._persist_context()
        return filters

    def _update_filters_for_module(self, session: SessionState, module: str, keys: list[str]) -> None:
        filters = self._prompt_filters(session, module, keys)
        print(f"[filters] {module}: {filters or 'sin filtros'}")

    def _clear_filters_for_module(self, session: SessionState, module: str) -> None:
        session.filters_by_module[module] = {}
        self._persist_context()
        print("[filters] Filtros limpiados. Tenant seleccionado preservado.")

    def _duplicate_related_filters(self, session: SessionState, module: str) -> None:
        related = {"stores": "users", "users": "stores"}
        target_module = related.get(module)
        if not target_module:
            print(f"[filters] {module} no tiene vista relacionada para duplicar filtros.")
            return

        source_filters = session.filters_by_module.get(module, {})
        if not source_filters:
            print(f"[filters] {module} no tiene filtros activos para duplicar.")
            return

        copied_keys = {"q", "status"}
        target_filters = session.filters_by_module.get(target_module, {}).copy()
        for key in copied_keys:
            if key in source_filters:
                target_filters[key] = source_filters[key]

        session.filters_by_module[target_module] = clean_filters(target_filters)
        self._persist_context()
        print(
            f"[filters] Duplicados {module} -> {target_module} "
            f"(tenant={session.selected_tenant_id or session.effective_tenant_id or 'N/A'}): "
            f"{session.filters_by_module[target_module] or 'sin filtros'}"
        )

    def _configure_sort(self, module: str, view_state: Any, columns: list[ColumnDef]) -> None:
        options = {column.key: column.label for column in columns}
        print(f"[sort] Columnas disponibles: {options}")
        selected = input("sort_by (vacío para quitar): ").strip()
        if not selected:
            view_state.sort_by = None
            view_state.sort_dir = "asc"
            print(f"[sort] Orden limpiado para {module}.")
            return
        if selected not in options:
            print(f"[sort] Columna inválida: {selected}")
            return
        direction = input("sort_dir (asc/desc): ").strip().lower() or "asc"
        view_state.sort_by = selected
        view_state.sort_dir = "desc" if direction == "desc" else "asc"
        print(f"[sort] Orden aplicado: {selected} {view_state.sort_dir}")

    def _configure_visible_columns(self, module: str, view_state: Any, columns: list[ColumnDef]) -> None:
        all_keys = [column.key for column in columns]
        current = set(view_state.visible_columns)
        print(f"[columns] Actuales ({module}): {sorted(current)}")
        print(f"[columns] Disponibles: {all_keys}")
        raw = input("columnas visibles (csv, vacío=mantener): ").strip()
        if not raw:
            return
        requested = [item.strip() for item in raw.split(",") if item.strip() in all_keys]
        if not requested:
            print("[columns] Selección inválida, se preserva configuración actual.")
            return
        view_state.visible_columns = requested
        print(f"[columns] Vista actualizada: {requested}")

    def _save_listing_view_state(self, session: SessionState, module: str, view_state: Any) -> None:
        session.listing_view_by_module[module] = serialize_view_state(view_state)
        self._persist_context()

    def _can_export_module(self, session: SessionState, module: str) -> bool:
        permissions = session.user.get("effective_permissions") if isinstance(session.user, dict) else None
        if isinstance(permissions, list) and permissions:
            required = {f"{module}.view", f"{module}.read", "admin.read"}
            return bool(required.intersection(set(str(item) for item in permissions)))
        return bool(session.role)

    def _print_validation_error(self, message: str, code: str = "UI_VALIDATION") -> None:
        print_error_banner(
            {
                "category": "validación",
                "code": code,
                "message": message,
                "trace_id": None,
                "action": "Corregir formulario y reintentar",
            }
        )

    def _load_pagination_state(self, session: SessionState, module: str) -> PaginationState:
        current = session.pagination_by_module.get(module, {})
        page = int(current.get("page", 1) or 1)
        page_size = int(current.get("page_size", 20) or 20)
        return PaginationState(page=max(page, 1), page_size=max(page_size, 1))

    def _save_pagination_state(self, session: SessionState, module: str, page_state: PaginationState) -> None:
        previous = session.pagination_by_module.get(module)
        updated = {"page": page_state.page, "page_size": page_state.page_size}
        if previous == updated:
            return
        session.pagination_by_module[module] = updated
        self._persist_context()

    def _persist_context(self) -> None:
        if self._on_context_updated:
            self._on_context_updated()

    def _invalidate_read_cache(self, module: str) -> None:
        self._listing_cache.invalidate_prefix(f"{module}:")

    def _cache_key(self, module: str, session: SessionState, page: int, page_size: int) -> str:
        filters = session.filters_by_module.get(module, {})
        filters_fingerprint = "|".join(f"{key}={filters[key]}" for key in sorted(filters.keys()))
        tenant_key = session.selected_tenant_id or session.effective_tenant_id or "NO_TENANT"
        return f"{module}:{session.session_fingerprint()}:{tenant_key}:{page}:{page_size}:{filters_fingerprint}"

    def _fetch_listing_with_cache(
        self,
        module: str,
        session: SessionState,
        page: int,
        page_size: int,
        fetch_page: Callable[[int, int], dict[str, Any]],
        force_refresh: bool,
    ) -> dict[str, Any]:
        key = self._cache_key(module, session, page, page_size)
        if not force_refresh:
            cached = self._listing_cache.get(key)
            if cached is not None:
                return cached

        start = time.monotonic()
        for attempt in range(1, 4):
            try:
                listing = fetch_page(page, page_size)
                self._listing_cache.set(key, listing)
                self._last_refresh_at_by_module[module] = time.time()
                elapsed = time.monotonic() - start
                elapsed_ms = int(elapsed * 1000)
                self._last_load_duration_ms_by_module[module] = elapsed_ms
                self._health_status_by_module[module] = "DEGRADED" if elapsed >= 1.2 else "OK"
                self.support_center.record_operation(module=module, screen=module, action="list", result="success", latency_ms=elapsed_ms, code="OK", message="listado actualizado")
                if elapsed >= 1.2:
                    print("[network] Conexión lenta, la respuesta demoró más de lo habitual.")
                if attempt > 1:
                    print("[network] Servicio recuperado. Continuando operación.")
                return listing
            except ApiError as error:
                self.support_center.record_operation(module=module, screen=module, action="list", result="error", latency_ms=int((time.monotonic() - start) * 1000), trace_id=error.trace_id, code=error.code, message=error.message)
                if error.code == "NETWORK_ERROR":
                    self._health_status_by_module[module] = "OFFLINE"
                    print("[network] Sin conexión. Verifica red/VPN y vuelve a intentar.")
                elif error.status_code and error.status_code >= 500:
                    self._health_status_by_module[module] = "DEGRADED"
                if self._is_retryable_listing_error(error) and attempt < 3:
                    print(f"[network] Reintentando... intento {attempt + 1}/3")
                    time.sleep(0.25 * attempt)
                    continue
                raise

    @staticmethod
    def _is_retryable_listing_error(error: ApiError) -> bool:
        return error.code in {"NETWORK_ERROR"} or bool(error.status_code and error.status_code >= 500)


def _print_context_header(
    session: SessionState,
    listing: dict[str, Any],
    last_refresh_at: float | None = None,
    load_duration_ms: int | None = None,
    health_status: str = "OK",
) -> None:
    total = listing.get("total")
    total_text = str(total) if total is not None else "N/A"
    print("\nContexto:")
    print(f"  actor_role: {session.role}")
    print(f"  effective_tenant_id: {session.effective_tenant_id}")
    print(f"  selected_tenant_id: {session.selected_tenant_id if is_superadmin(session.role) else 'N/A'}")
    print(f"  page: {listing.get('page')} / page_size: {listing.get('page_size')} / total: {total_text}")
    if last_refresh_at is not None:
        print(f"  última actualización: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_refresh_at))}")
    if load_duration_ms is not None:
        print(f"  duración carga aprox: {load_duration_ms}ms")
    print(f"  salud vista: {health_status}")


def _api_error_diagnostic(error: ApiError) -> str:
    if error.code == "NETWORK_ERROR":
        return "No se pudo conectar al API. Revisa URL base, red/VPN y estado del servicio."
    if error.status_code == 401:
        return "Sesión expirada o token inválido. Ejecuta Login nuevamente."
    if error.status_code == 403:
        return "Sin permisos para esta operación en el tenant/store seleccionado."
    if error.status_code == 404:
        return "Recurso no encontrado. Valida IDs y tenant operativo activo."
    if error.status_code and error.status_code >= 500:
        return "Falla interna del API. Comparte trace_id con soporte para trazabilidad."
    return "Revisa payload/filtros y vuelve a intentar."
