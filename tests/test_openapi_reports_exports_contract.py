from app.main import app


def test_openapi_reports_exports_contract_is_explicit():
    openapi = app.openapi()
    paths = openapi["paths"]
    schemas = openapi["components"]["schemas"]

    create_export_schema = schemas["ExportCreateRequest"]
    assert create_export_schema["properties"]["source_type"]["$ref"]
    assert create_export_schema["properties"]["format"]["$ref"]
    create_example = create_export_schema["example"]

    source_type_schema = schemas["ExportSourceType"]
    assert source_type_schema["enum"] == ["reports_overview", "reports_daily", "reports_calendar"]

    format_schema = schemas["ExportFormat"]
    assert "csv" in format_schema["enum"]
    assert "xlsx" in format_schema["enum"]

    status_schema = schemas["ExportStatus"]
    assert status_schema["enum"] == ["CREATED", "READY", "FAILED"]
    assert "CREATED" in status_schema["description"]
    assert "READY" in status_schema["description"]
    assert "FAILED" in status_schema["description"]

    export_response_example = schemas["ExportResponse"]["example"]
    assert export_response_example["source_type"] == create_example["source_type"]
    assert export_response_example["format"] == create_example["format"]
    assert export_response_example["file_name"] == create_example["file_name"]

    download_responses = paths["/aris3/exports/{export_id}/download"]["get"]["responses"]
    content = download_responses["200"]["content"]
    assert "text/csv" in content
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content
    assert "application/octet-stream" in content
    assert "application/json" not in content
    assert content["text/csv"]["schema"] == {"type": "string", "format": "binary"}
    assert content["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    assert content["application/octet-stream"]["schema"] == {"type": "string", "format": "binary"}
    assert "headers" in download_responses["200"]
    assert download_responses["200"]["headers"]["Content-Type"]["schema"]["type"] == "string"
    assert download_responses["200"]["headers"]["Content-Disposition"]["schema"]["type"] == "string"
    assert download_responses["200"]["headers"]["Content-Length"]["schema"]["type"] == "integer"

    get_export_404 = paths["/aris3/exports/{export_id}"]["get"]["responses"]["404"]["content"]["application/json"]["example"]
    download_404 = download_responses["404"]["content"]["application/json"]["example"]
    assert get_export_404 == download_404
    assert get_export_404["code"] == "RESOURCE_NOT_FOUND"
    assert get_export_404["message"] == "Resource not found"
    assert get_export_404["details"]["message"] == "export not found"
    assert get_export_404["details"]["export_id"]

    list_parameters = paths["/aris3/exports"]["get"]["parameters"]
    page_size = next(param for param in list_parameters if param["name"] == "page_size")
    assert "Default: 200" in page_size["description"]
    assert "Maximum allowed: 200" in page_size["description"]

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
