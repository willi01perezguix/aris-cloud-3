from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from clients.aris3_client_sdk.auth_client import AuthClient
from clients.aris3_client_sdk.config import SDKConfig
from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.http_client import HttpClient
from clients.aris3_client_sdk.me_client import MeClient

from aris_control_2.app.context_store import restore_compatible_context, save_context
from aris_control_2.app.diagnostics import APP_VERSION, ConnectivityResult, build_diagnostic_report, report_to_text, run_health_check
from aris_control_2.app.error_presenter import build_error_payload
from aris_control_2.app.operational_support import OperationalSupportCenter, build_support_package, format_technical_summary
from aris_control_2.app.state import SessionState


@dataclass(frozen=True)
class LoginResult:
    success: bool
    message: str
    trace_id: str | None = None


class GuiController:
    def __init__(
        self,
        *,
        config: SDKConfig | None = None,
        http_client: HttpClient | None = None,
        auth_client: AuthClient | None = None,
        me_client: MeClient | None = None,
        session: SessionState | None = None,
        support_center: OperationalSupportCenter | None = None,
        environment: str | None = None,
    ) -> None:
        self.config = config or SDKConfig.from_env()
        self.environment = (environment or os.getenv("ARIS3_ENV", "dev")).strip().lower() or "dev"
        self.http_client = http_client or HttpClient(config=self.config)
        self.auth_client = auth_client or AuthClient(self.http_client)
        self.me_client = me_client or MeClient(self.http_client)
        self.session = session or SessionState()
        self.support_center = support_center or OperationalSupportCenter.load()
        self.last_error: dict[str, Any] | None = None
        self.connectivity = run_health_check(self.http_client)

    def status_snapshot(self) -> dict[str, str]:
        return {
            "connectivity": self.connectivity.status,
            "base_url": self.config.base_url,
            "version": APP_VERSION,
        }

    def refresh_connectivity(self) -> ConnectivityResult:
        self.connectivity = run_health_check(self.http_client)
        return self.connectivity

    def login(self, *, username_or_email: str, password: str) -> LoginResult:
        if not username_or_email.strip() or not password.strip():
            return LoginResult(success=False, message="Completa usuario y contraseña.")

        started = perf_counter()
        try:
            response = self.auth_client.login(username_or_email=username_or_email.strip(), password=password)
            self.session.access_token = response.get("access_token")
            self.session.refresh_token = response.get("refresh_token")
            self.session.must_change_password = bool(response.get("must_change_password", False))

            me_payload = self.me_client.get_me(access_token=self.session.access_token or "")
            self.session.apply_me(me_payload)
            self._restore_operator_context()

            latency_ms = int((perf_counter() - started) * 1000)
            self.support_center.record_operation(
                module="auth",
                screen="login",
                action="login",
                result="success",
                latency_ms=latency_ms,
                code="OK",
                message="login ok",
            )
            self.last_error = None
            return LoginResult(success=True, message="Inicio de sesión exitoso.")
        except ApiError as error:
            payload = build_error_payload(error)
            self.last_error = payload
            self.support_center.record_incident(module="auth", payload=payload)
            return LoginResult(
                success=False,
                message=str(payload.get("message") or "No fue posible iniciar sesión."),
                trace_id=payload.get("trace_id"),
            )
        except Exception as error:  # noqa: BLE001
            payload = build_error_payload(error)
            self.last_error = payload
            self.support_center.record_incident(module="auth", payload=payload)
            return LoginResult(success=False, message="Error inesperado al iniciar sesión.", trace_id=payload.get("trace_id"))

    def diagnostic_text(self) -> str:
        report = build_diagnostic_report(
            base_url=self.config.base_url,
            environment=self.environment,
            module=self.session.current_module,
            connectivity=self.connectivity,
            last_error=self.last_error,
        )
        return report_to_text(report)

    def export_support_package(self, *, output_dir: Path | None = None) -> tuple[Path, Path]:
        target = output_dir or Path("out") / "reports"
        package = build_support_package(
            base_url=self.config.base_url,
            environment=self.environment,
            current_module=self.session.current_module,
            selected_tenant_id=self.session.selected_tenant_id,
            active_filters=self.session.filters_by_module,
            incidents=self.support_center.incidents,
            operations=self.support_center.operations,
        )
        return _export_support_files(package=package, output_dir=target)

    def support_summary(self) -> str:
        package = build_support_package(
            base_url=self.config.base_url,
            environment=self.environment,
            current_module=self.session.current_module,
            selected_tenant_id=self.session.selected_tenant_id,
            active_filters=self.session.filters_by_module,
            incidents=self.support_center.incidents,
            operations=self.support_center.operations,
        )
        return format_technical_summary(package=package)

    def _restore_operator_context(self) -> None:
        payload = restore_compatible_context(session_fingerprint=self.session.session_fingerprint())
        if not payload:
            return
        self.session.selected_tenant_id = payload.get("selected_tenant_id")
        restored_filters = payload.get("filters_by_module")
        if isinstance(restored_filters, dict):
            self.session.filters_by_module = {
                str(key): value for key, value in restored_filters.items() if isinstance(value, dict)
            }
        restored_pagination = payload.get("pagination_by_module")
        if isinstance(restored_pagination, dict):
            self.session.pagination_by_module = {
                str(key): value for key, value in restored_pagination.items() if isinstance(value, dict)
            }
        restored_listing_view = payload.get("listing_view_by_module")
        if isinstance(restored_listing_view, dict):
            self.session.listing_view_by_module = {
                str(key): value for key, value in restored_listing_view.items() if isinstance(value, dict)
            }

    def persist_operator_context(self) -> None:
        if not self.session.role:
            return
        save_context(
            session_fingerprint=self.session.session_fingerprint(),
            selected_tenant_id=self.session.selected_tenant_id,
            filters_by_module=self.session.filters_by_module,
            pagination_by_module=self.session.pagination_by_module,
            listing_view_by_module=self.session.listing_view_by_module,
        )


def _export_support_files(*, package: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"soporte-{stamp}.json"
    txt_path = output_dir / f"soporte-{stamp}.txt"
    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text(format_technical_summary(package=package), encoding="utf-8")
    return json_path, txt_path
