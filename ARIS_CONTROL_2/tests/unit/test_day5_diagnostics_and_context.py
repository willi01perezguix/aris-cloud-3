from pathlib import Path

from aris_control_2.app.context_store import clear_context, restore_compatible_context, save_context
from aris_control_2.app.diagnostics import classify_connectivity, sanitize_report


def test_connectivity_parser_states() -> None:
    assert classify_connectivity(latency_ms=150, error_code=None) == "Conectado"
    assert classify_connectivity(latency_ms=1800, error_code=None) == "Degradado"
    assert classify_connectivity(latency_ms=None, error_code="NETWORK_ERROR") == "Sin conexión"


def test_report_sanitization_removes_sensitive_fields() -> None:
    report = {
        "base_url": "https://aris-cloud-3-api-pecul.ondigitalocean.app/",
        "token": "secret-token",
        "nested": {"password": "abc", "trace_id": "trace-1", "message": "boom"},
    }

    sanitized = sanitize_report(report)

    assert "token" not in sanitized
    assert "password" not in sanitized["nested"]
    assert sanitized["nested"]["trace_id"] == "trace-1"


def test_persistence_restores_tenant_and_filters_and_clears_incompatible(tmp_path: Path, monkeypatch) -> None:
    context_file = tmp_path / "operator-context.json"
    monkeypatch.setenv("ARIS3_OPERATOR_CONTEXT_PATH", str(context_file))

    save_context(
        session_fingerprint="SUPERADMIN:t-1",
        selected_tenant_id="tenant-a",
        filters_by_module={"stores": {"status": "ACTIVE"}},
    )

    restored = restore_compatible_context(session_fingerprint="SUPERADMIN:t-1")
    assert restored["selected_tenant_id"] == "tenant-a"
    assert restored["filters_by_module"]["stores"]["status"] == "ACTIVE"

    incompatible = restore_compatible_context(session_fingerprint="MANAGER:t-2")
    assert incompatible == {}
    assert not context_file.exists()

    clear_context()
