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

    format_schema = schemas["ExportFormat"]
    assert "csv" in format_schema["enum"]
    assert "xlsx" in format_schema["enum"]

    status_schema = schemas["ExportStatus"]
    assert status_schema["enum"] == ["CREATED", "READY", "FAILED"]

    download_responses = paths["/aris3/exports/{export_id}/download"]["get"]["responses"]
    content = download_responses["200"]["content"]
    assert "text/csv" in content
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content
    assert "application/octet-stream" in content
    assert "application/json" not in content
    assert content["text/csv"]["schema"] == {"type": "string", "format": "binary"}
    assert "headers" in download_responses["200"]

    assert download_responses["404"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/NotFoundErrorResponse"
    assert download_responses["409"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ConflictErrorResponse"
    assert download_responses["422"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ValidationErrorResponse"

    assert "ReportDailyRow" in schemas
    assert "ReportCalendarRow" in schemas
    assert "ReportMeta" in schemas
    assert "ReportTotals" in schemas
    assert "ReportFilters" in schemas
    assert "ValidationErrorResponse" in schemas
    assert "BusinessErrorResponse" in schemas

    report_daily_422 = paths["/aris3/reports/daily"]["get"]["responses"]["422"]
    assert report_daily_422["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ValidationErrorResponse"
