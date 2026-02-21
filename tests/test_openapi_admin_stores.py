from app.main import app


def test_create_store_openapi_has_single_query_tenant_id_parameter():
    operation = app.openapi()["paths"]["/aris3/admin/stores"]["post"]

    query_tenant_params = [
        param for param in operation.get("parameters", []) if param.get("name") == "query_tenant_id"
    ]

    assert len(query_tenant_params) == 1
    assert query_tenant_params[0]["in"] == "query"
    assert "Legacy tenant selector for compatibility" in (query_tenant_params[0].get("description") or "")
    assert [param for param in operation.get("parameters", []) if param.get("name") == "tenant_id"] == []
    assert "Canonical source" in (operation.get("description") or "")

    request_body_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = request_body_ref.rsplit("/", 1)[-1]
    store_schema = app.openapi()["components"]["schemas"][schema_name]

    assert "tenant_id" in store_schema["properties"]
    assert "Canonical tenant for store creation" in (
        store_schema["properties"]["tenant_id"].get("description") or ""
    )
