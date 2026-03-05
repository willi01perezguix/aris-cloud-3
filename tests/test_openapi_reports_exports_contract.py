from app.main import app


def test_openapi_reports_exports_contract_is_explicit():
    openapi = app.openapi()
    paths = openapi["paths"]
    schemas = openapi["components"]["schemas"]

    create_export_schema = schemas["ExportCreateRequest"]
    assert create_export_schema["properties"]["source_type"]["$ref"]
    assert create_export_schema["properties"]["format"]["$ref"]

    source_type_schema = schemas["ExportSourceType"]
    assert source_type_schema["enum"] == ["reports_overview", "reports_daily", "reports_calendar"]

    download_response = paths["/aris3/exports/{export_id}/download"]["get"]["responses"]["200"]
    content = download_response["content"]
    assert "text/csv" in content
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content

    assert "DailyRow" in schemas
    assert "CalendarRow" in schemas
    assert "ReportMeta" in schemas
    assert "ReportTotals" in schemas
