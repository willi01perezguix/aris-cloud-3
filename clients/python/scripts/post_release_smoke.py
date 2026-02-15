from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.exports_client import ExportsClient
from aris3_client_sdk.config import ConfigError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.models_exports import ExportRequest
from aris3_client_sdk.models_reports import ReportFilter
from aris3_client_sdk.tracing import TraceContext


@dataclass
class SmokeCheck:
    name: str
    passed: bool
    details: str


def _build_http(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


def check_config_strict() -> SmokeCheck:
    previous_base = os.environ.pop("ARIS3_API_BASE_URL", None)
    previous_dev = os.environ.pop("ARIS3_API_BASE_URL_DEV", None)
    previous_staging = os.environ.pop("ARIS3_API_BASE_URL_STAGING", None)

    try:
        try:
            load_config()
        except ConfigError:
            return SmokeCheck(
                name="load_config_requires_api_base_url",
                passed=True,
                details="ConfigError recibido correctamente sin ARIS3_API_BASE_URL.",
            )
        return SmokeCheck(
            name="load_config_requires_api_base_url",
            passed=False,
            details="Se esperaba ConfigError y load_config() no falló.",
        )
    finally:
        if previous_base is not None:
            os.environ["ARIS3_API_BASE_URL"] = previous_base
        if previous_dev is not None:
            os.environ["ARIS3_API_BASE_URL_DEV"] = previous_dev
        if previous_staging is not None:
            os.environ["ARIS3_API_BASE_URL_STAGING"] = previous_staging


@responses.activate
def check_export_polling_flow() -> SmokeCheck:
    os.environ["ARIS3_API_BASE_URL"] = "https://api.example.com"
    http = _build_http("https://api.example.com")
    client = ExportsClient(http=http, access_token="token")

    created = {
        "export_id": "exp-smoke",
        "tenant_id": "tenant-1",
        "store_id": "store-1",
        "source_type": "reports_daily",
        "format": "csv",
        "filters_snapshot": {},
        "status": "CREATED",
        "row_count": 0,
        "checksum_sha256": None,
        "failure_reason_code": None,
        "generated_by_user_id": "u1",
        "generated_at": None,
        "trace_id": "trace-1",
        "file_size_bytes": None,
        "content_type": None,
        "file_name": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": None,
    }
    ready = {
        **created,
        "status": "READY",
        "file_name": "report.csv",
        "content_type": "text/csv",
        "file_size_bytes": 128,
        "checksum_sha256": "sha256-smoke",
    }

    responses.add(responses.POST, "https://api.example.com/aris3/exports", json=created, status=201)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-smoke", json=created, status=200)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-smoke", json=ready, status=200)

    try:
        request = ExportRequest(
            source_type="reports_daily",
            format="csv",
            filters=ReportFilter(store_id="store-1"),
            transaction_id="txn-smoke",
        )
        status = client.request_export(request, idempotency_key="idem-smoke")
        final = client.wait_for_export_ready("exp-smoke", timeout_sec=2.0, poll_interval_sec=0.01)
        if status.export_id != "exp-smoke" or final.status.status != "READY":
            return SmokeCheck(
                name="request_export_wait_ready_flow",
                passed=False,
                details="El flujo CREATED->READY no produjo el estado esperado.",
            )
        return SmokeCheck(
            name="request_export_wait_ready_flow",
            passed=True,
            details="Flujo CREATED->READY validado con request_export + wait_for_export_ready.",
        )
    except Exception as exc:  # noqa: BLE001
        return SmokeCheck(
            name="request_export_wait_ready_flow",
            passed=False,
            details=f"Fallo inesperado en flujo de export: {type(exc).__name__}: {exc}",
        )


@responses.activate
def check_get_cache_stays_enabled_outside_polling() -> SmokeCheck:
    os.environ["ARIS3_API_BASE_URL"] = "https://api.example.com"
    http = _build_http("https://api.example.com")

    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={"value": 7},
        status=200,
    )

    try:
        first = http.request("GET", "/aris3/reports/overview")
        second = http.request("GET", "/aris3/reports/overview")
        if first != {"value": 7} or second != {"value": 7}:
            return SmokeCheck(
                name="get_cache_normal_behavior",
                passed=False,
                details="Respuesta inesperada en GET cacheable.",
            )
        if len(responses.calls) != 1:
            return SmokeCheck(
                name="get_cache_normal_behavior",
                passed=False,
                details="Se esperaban 1 request HTTP real por caché activa.",
            )
        return SmokeCheck(
            name="get_cache_normal_behavior",
            passed=True,
            details="La caché GET sigue activa fuera del polling (cache hit confirmado).",
        )
    except Exception as exc:  # noqa: BLE001
        return SmokeCheck(
            name="get_cache_normal_behavior",
            passed=False,
            details=f"Fallo inesperado al validar caché GET: {type(exc).__name__}: {exc}",
        )


def main() -> int:
    checks = [
        check_config_strict(),
        check_export_polling_flow(),
        check_get_cache_stays_enabled_outside_polling(),
    ]
    success = all(item.passed for item in checks)

    output = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "suite": "post_release_smoke",
        "checks": [asdict(item) for item in checks],
        "summary": {
            "passed": sum(1 for item in checks if item.passed),
            "failed": sum(1 for item in checks if not item.passed),
            "ok": success,
        },
    }

    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifacts_dir / "post_release_smoke_result.json"
    log_path = artifacts_dir / "post_release_smoke_result.log"
    json_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = ["post_release_smoke"]
    for item in checks:
        mark = "PASS" if item.passed else "FAIL"
        lines.append(f"[{mark}] {item.name}: {item.details}")
    lines.append(f"overall={'PASS' if success else 'FAIL'}")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
