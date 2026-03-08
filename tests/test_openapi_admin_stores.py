from app.main import app


def test_create_store_openapi_uses_canonical_body_tenant_id_only():
    operation = app.openapi()["paths"]["/aris3/admin/stores"]["post"]

    query_tenant_params = [
        param for param in operation.get("parameters", []) if param.get("name") == "query_tenant_id"
    ]
    assert query_tenant_params == []
    description = operation.get("description") or ""
    assert "Canonical input" in description
    assert "Legacy compatibility" not in description

    request_body_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = request_body_ref.rsplit("/", 1)[-1]
    store_schema = app.openapi()["components"]["schemas"][schema_name]

    assert "tenant_id" in store_schema["properties"]
    assert "Canonical tenant for store creation" in (
        store_schema["properties"]["tenant_id"].get("description") or ""
    )
