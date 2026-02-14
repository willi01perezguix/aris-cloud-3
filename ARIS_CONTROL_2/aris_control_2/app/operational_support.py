from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from aris_control_2.app.diagnostics import APP_VERSION, sanitize_report

DEFAULT_INCIDENTS_PATH = Path.home() / ".aris_control_2_incidents.json"
MAX_INCIDENTS = 80
MAX_OPERATIONS = 120


@dataclass
class OperationalSupportCenter:
    incidents: list[dict[str, Any]]
    operations: list[dict[str, Any]]

    @classmethod
    def load(cls) -> OperationalSupportCenter:
        payload = _load_payload()
        return cls(
            incidents=payload.get("incidents", []),
            operations=payload.get("operations", []),
        )

    def save(self) -> None:
        payload = {
            "incidents": self.incidents[-MAX_INCIDENTS:],
            "operations": self.operations[-MAX_OPERATIONS:],
        }
        path = _incidents_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear_incidents(self) -> None:
        self.incidents = []
        self.save()

    def record_operation(
        self,
        *,
        module: str,
        screen: str,
        action: str,
        result: str,
        latency_ms: int,
        trace_id: str | None = None,
        code: str | None = None,
        message: str | None = None,
    ) -> None:
        event = sanitize_report(
            {
                "timestamp": _now_iso(),
                "module": module,
                "screen": screen,
                "action": action,
                "result": result,
                "latency_ms": latency_ms,
                "trace_id": trace_id,
                "code": code,
                "message": message,
            }
        )
        self.operations.append(event)
        self.save()

    def record_incident(self, *, module: str, payload: dict[str, Any], status: str = "abierto") -> dict[str, Any]:
        incident = sanitize_report(
            {
                "timestamp": _now_iso(),
                "timestamp_local": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                "module": module,
                "status": status,
                "code": payload.get("code"),
                "message": payload.get("message"),
                "trace_id": payload.get("trace_id"),
            }
        )
        self.incidents.append(incident)
        self.save()
        return incident

    def mark_module_mitigated(self, module: str) -> None:
        for incident in reversed(self.incidents):
            if incident.get("module") == module and incident.get("status") == "abierto":
                incident["status"] = "mitigado"
                break
        self.save()

    def latest_incident_by_module(self, modules: list[str]) -> list[dict[str, Any]]:
        latest: list[dict[str, Any]] = []
        for module in modules:
            match = next((item for item in reversed(self.incidents) if item.get("module") == module), None)
            if match:
                latest.append(match)
        return latest


def build_support_package(
    *,
    base_url: str,
    environment: str,
    current_module: str,
    selected_tenant_id: str | None,
    active_filters: dict[str, dict[str, str]],
    incidents: list[dict[str, Any]],
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "diagnostico": {
            "timestamp": _now_iso(),
            "base_url": base_url,
            "app_version": APP_VERSION,
            "environment": environment,
            "current_module": current_module,
        },
        "incidencias_recientes": incidents[-20:],
        "contexto_operativo": {
            "selected_tenant_id": selected_tenant_id,
            "active_filters": active_filters,
            "operations_recientes": operations[-30:],
        },
    }
    return sanitize_report(payload)


def format_technical_summary(*, package: dict[str, Any]) -> str:
    diagnostics = package.get("diagnostico", {})
    incidents = package.get("incidencias_recientes", [])
    last = incidents[-1] if incidents else {}
    return (
        f"ARIS_CONTROL_2 soporte | app={diagnostics.get('app_version')} env={diagnostics.get('environment')} "
        f"base_url={diagnostics.get('base_url')} module={diagnostics.get('current_module')} "
        f"incidencias={len(incidents)} last_code={last.get('code', 'N/A')} last_trace_id={last.get('trace_id', 'N/A')}"
    )


def _incidents_path() -> Path:
    configured = os.getenv("ARIS3_INCIDENTS_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_INCIDENTS_PATH


def _load_payload() -> dict[str, Any]:
    path = _incidents_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()
