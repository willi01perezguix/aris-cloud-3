from aris_control_2.app.operational_support import (
    MAX_INCIDENTS,
    OperationalSupportCenter,
    build_support_package,
    format_technical_summary,
)


def test_support_export_sanitizes_sensitive_data() -> None:
    package = build_support_package(
        base_url="https://aris-cloud-3-api-pecul.ondigitalocean.app/",
        environment="dev",
        current_module="users",
        selected_tenant_id="tenant-1",
        active_filters={"users": {"q": "ana", "token": "hidden"}},
        incidents=[{"module": "users", "message": "boom", "trace_id": "tr-1", "authorization": "secret"}],
        operations=[{"module": "users", "password": "123", "result": "error"}],
    )

    assert "token" not in package["contexto_operativo"]["active_filters"]["users"]
    assert "authorization" not in package["incidencias_recientes"][0]
    assert "password" not in package["contexto_operativo"]["operations_recientes"][0]


def test_incidents_rotation_persists_recent_entries(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_INCIDENTS_PATH", str(tmp_path / "incidents.json"))
    center = OperationalSupportCenter.load()

    for idx in range(MAX_INCIDENTS + 8):
        center.record_incident(module="users", payload={"code": f"E{idx}", "message": "err", "trace_id": None})

    restored = OperationalSupportCenter.load()
    assert len(restored.incidents) == MAX_INCIDENTS
    assert restored.incidents[0]["code"] == "E8"
    assert restored.incidents[-1]["code"] == f"E{MAX_INCIDENTS + 7}"


def test_technical_summary_has_support_fields() -> None:
    package = build_support_package(
        base_url="https://aris-cloud-3-api-pecul.ondigitalocean.app/",
        environment="prod",
        current_module="stores",
        selected_tenant_id="tenant-a",
        active_filters={"stores": {"status": "ACTIVE"}},
        incidents=[{"code": "HTTP_500", "trace_id": "trace-99"}],
        operations=[],
    )

    summary = format_technical_summary(package=package)

    assert "ARIS_CONTROL_2 soporte" in summary
    assert "env=prod" in summary
    assert "incidencias=1" in summary
    assert "last_trace_id=trace-99" in summary
