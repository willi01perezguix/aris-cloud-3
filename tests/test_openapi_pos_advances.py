from app.main import app


def test_pos_advances_endpoints_are_published_in_openapi():
    paths = app.openapi()["paths"]

    expected = {
        "/aris3/pos/advances": {"get", "post"},
        "/aris3/pos/advances/{advance_id}": {"get"},
        "/aris3/pos/advances/lookup": {"get"},
        "/aris3/pos/advances/{advance_id}/actions": {"post"},
        "/aris3/pos/advances/alerts": {"get"},
    }

    for path, methods in expected.items():
        assert path in paths
        assert methods.issubset(set(paths[path].keys()))


def test_pos_advances_critical_public_fields_and_alert_contract_are_documented():
    openapi = app.openapi()
    summary_schema = openapi["components"]["schemas"]["PosAdvanceSummary"]
    assert "advance_number" in summary_schema["properties"]
    assert "barcode_value" in summary_schema["properties"]

    detail_schema = openapi["components"]["schemas"]["PosAdvanceDetailResponse"]
    assert "barcode_type" in detail_schema["properties"]
    assert "legal_notice" in detail_schema["properties"]

    alerts_schema = openapi["components"]["schemas"]["PosAdvanceAlertRow"]
    assert {"days_to_expiry", "amount", "advance_number"}.issubset(alerts_schema["properties"].keys())
