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

    download_responses = paths["/aris3/exports/{export_id}/download"]["get"]["responses"]
    content = download_responses["200"]["content"]
    assert "text/csv" in content
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content
    assert "application/octet-stream" in content
    assert "headers" in download_responses["200"]
    assert "422" in download_responses

    assert "ReportDailyRow" in schemas
    assert "ReportCalendarRow" in schemas
    assert "ReportMeta" in schemas
    assert "ReportTotals" in schemas
    assert "ReportFilters" in schemas
    assert "ValidationErrorResponse" in schemas
    assert "BusinessErrorResponse" in schemas
