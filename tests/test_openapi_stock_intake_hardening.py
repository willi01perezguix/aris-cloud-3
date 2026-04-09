from app.main import app


MUTATING_ENDPOINTS = [
    ("/aris3/stock/preload-sessions", "post"),
    ("/aris3/stock/preload-lines/{line_id}/save", "post"),
    ("/aris3/stock/pending-epc/{line_id}/assign-epc", "post"),
    ("/aris3/stock/epc/release", "post"),
    ("/aris3/catalog/sku/{sku}/images", "post"),
    ("/aris3/catalog/sku/{sku}/images/{asset_id}/primary", "put"),
    ("/aris3/stock/items/{item_uid}/mark-issue", "post"),
    ("/aris3/stock/items/{item_uid}/resolve-issue", "post"),
]


def test_intake_mutations_document_idempotency_key_header():
    openapi = app.openapi()
    for path, method in MUTATING_ENDPOINTS:
        operation = openapi["paths"][path][method]
        params = operation.get("parameters", [])
        idempotency = next((param for param in params if param["name"] == "Idempotency-Key"), None)

        assert idempotency is not None
        assert idempotency["in"] == "header"
        assert idempotency["required"] is False


def test_intake_mutation_conflicts_and_typed_responses_are_documented():
    openapi = app.openapi()

    release = openapi["paths"]["/aris3/stock/epc/release"]["post"]
    mark_issue = openapi["paths"]["/aris3/stock/items/{item_uid}/mark-issue"]["post"]
    resolve_issue = openapi["paths"]["/aris3/stock/items/{item_uid}/resolve-issue"]["post"]

    assert release["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/EpcReleaseResponse"
    assert mark_issue["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ItemIssueResponse"
    assert resolve_issue["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ItemIssueResolveResponse"

    assert release["responses"]["409"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ApiErrorResponse"
    assert mark_issue["responses"]["409"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ApiErrorResponse"
    assert resolve_issue["responses"]["409"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ApiErrorResponse"
