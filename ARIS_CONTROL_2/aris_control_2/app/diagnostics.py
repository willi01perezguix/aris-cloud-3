from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any
import json
import platform

from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.http_client import HttpClient

APP_VERSION = "v1.0.4-day5"
HEALTH_CHECK_PATH = "/health"
DEGRADED_LATENCY_MS = 1200
SENSITIVE_KEY_MARKERS = ("token", "password", "secret", "authorization", "api_key")


@dataclass(frozen=True)
class ConnectivityResult:
    status: str
    latency_ms: int | None
    checked_at: datetime
    message: str
    error_code: str | None = None
    trace_id: str | None = None


def classify_connectivity(*, latency_ms: int | None, error_code: str | None = None, degraded_threshold_ms: int = DEGRADED_LATENCY_MS) -> str:
    if error_code:
        return "Sin conexión"
    if latency_ms is None:
        return "Sin conexión"
    if latency_ms >= degraded_threshold_ms:
        return "Degradado"
    return "Conectado"


def run_health_check(http_client: HttpClient) -> ConnectivityResult:
    checked_at = datetime.now().astimezone()
    started = perf_counter()
    try:
        http_client.request("GET", HEALTH_CHECK_PATH)
        latency_ms = int((perf_counter() - started) * 1000)
        return ConnectivityResult(
            status=classify_connectivity(latency_ms=latency_ms),
            latency_ms=latency_ms,
            checked_at=checked_at,
            message="Health check exitoso",
        )
    except ApiError as error:
        return ConnectivityResult(
            status=classify_connectivity(latency_ms=None, error_code=error.code),
            latency_ms=None,
            checked_at=checked_at,
            message=error.message,
            error_code=error.code,
            trace_id=error.trace_id,
        )


def build_diagnostic_report(*, base_url: str, environment: str, module: str, connectivity: ConnectivityResult | None, last_error: dict[str, Any] | None) -> dict[str, Any]:
    now = datetime.now().astimezone()
    report: dict[str, Any] = {
        "timestamp": now.isoformat(),
        "base_url": base_url,
        "module": module,
        "app_version": APP_VERSION,
        "environment": environment,
        "os": platform.platform(),
        "connectivity": _connectivity_payload(connectivity),
        "last_error": last_error or {},
    }
    return sanitize_report(report)


def report_to_text(report: dict[str, Any]) -> str:
    lines = ["ARIS_CONTROL_2 - Reporte de diagnóstico"]
    for key, value in report.items():
        serialized = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        lines.append(f"{key}: {serialized}")
    return "\n".join(lines)


def sanitize_report(payload: dict[str, Any]) -> dict[str, Any]:
    return _sanitize_value(payload)


def _sanitize_value(value: Any, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            lowered = key.lower()
            if any(marker in lowered for marker in SENSITIVE_KEY_MARKERS):
                continue
            sanitized[key] = _sanitize_value(nested, key)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item, parent_key) for item in value]
    return value


def _connectivity_payload(connectivity: ConnectivityResult | None) -> dict[str, Any]:
    if connectivity is None:
        return {}
    return {
        "status": connectivity.status,
        "latency_ms": connectivity.latency_ms,
        "checked_at": connectivity.checked_at.isoformat(),
        "message": connectivity.message,
        "error_code": connectivity.error_code,
        "trace_id": connectivity.trace_id,
    }
