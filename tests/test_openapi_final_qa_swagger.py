from app.main import app


ADMIN_ACCESS_CONTROL_PATH_PREFIX = "/aris3/admin/access-control"


def _response_schema(response: dict) -> dict | None:
    return response.get("content", {}).get("application/json", {}).get("schema")


def test_admin_store_create_documents_legacy_query_tenant_id_without_duplicates():
    post_operation = app.openapi()["paths"]["/aris3/admin/stores"]["post"]
    query_params = [
        param
        for param in post_operation.get("parameters", [])
        if param.get("in") == "query" and param.get("name") == "query_tenant_id"
    ]

    assert len(query_params) == 1
    assert query_params[0].get("deprecated") is True

    description = post_operation.get("description") or ""
    assert "Canonical input" in description
    assert "body.tenant_id" in description or "tenant_id" in description
    assert "backward compatibility" in description
    assert "must match" in description
    assert "SUPERADMIN" in description and "PLATFORM_ADMIN" in description


def test_admin_users_list_parameters_have_clean_descriptions_without_visual_artifacts():
    get_operation = app.openapi()["paths"]["/aris3/admin/users"]["get"]

    for parameter in get_operation.get("parameters", []):
        description = parameter.get("description")
        if description is None:
            continue
        assert "--" not in description
        assert description.strip() == description

    is_active_param = next(p for p in get_operation["parameters"] if p["name"] == "is_active")
    assert is_active_param["description"] == "Filter by active status (`true` or `false`)."


def test_admin_permission_catalog_has_non_empty_documented_responses_with_schema():
    get_operation = app.openapi()["paths"]["/aris3/admin/access-control/permission-catalog"]["get"]

    assert "200" in get_operation["responses"]
    assert "422" in get_operation["responses"]

    response_200_schema = _response_schema(get_operation["responses"]["200"])
    assert response_200_schema == {"$ref": "#/components/schemas/PermissionCatalogResponse"}

    component = app.openapi()["components"]["schemas"]["PermissionCatalogResponse"]
    assert "permissions" in component["properties"]
    assert "trace_id" in component["properties"]
    assert get_operation.get("deprecated") is not True


def test_openapi_summaries_use_consistent_sentence_case_for_core_admin_crud():
    paths = app.openapi()["paths"]
    assert paths["/aris3/admin/tenants"]["get"]["summary"] == "List tenants"
    assert paths["/aris3/admin/tenants"]["post"]["summary"] == "Create tenant"
    assert paths["/aris3/admin/tenants/{tenant_id}"]["get"]["summary"] == "Get tenant"
    assert paths["/aris3/admin/tenants/{tenant_id}"]["patch"]["summary"] == "Update tenant"
    assert paths["/aris3/admin/tenants/{tenant_id}"]["delete"]["summary"] == "Delete tenant"

    assert paths["/aris3/admin/stores"]["get"]["summary"] == "List stores"
    assert paths["/aris3/admin/stores"]["post"]["summary"] == "Create store"
    assert paths["/aris3/admin/stores/{store_id}"]["get"]["summary"] == "Get store"
    assert paths["/aris3/admin/stores/{store_id}"]["patch"]["summary"] == "Update store"
    assert paths["/aris3/admin/stores/{store_id}"]["delete"]["summary"] == "Delete store"

    assert paths["/aris3/admin/users"]["get"]["summary"] == "List users"
    assert paths["/aris3/admin/users"]["post"]["summary"] == "Create user"
    assert paths["/aris3/admin/users/{user_id}"]["get"]["summary"] == "Get user"
    assert paths["/aris3/admin/users/{user_id}"]["patch"]["summary"] == "Update user"
    assert paths["/aris3/admin/users/{user_id}"]["delete"]["summary"] == "Delete user"


def test_scoped_permission_catalog_description_is_clear_and_canonical():
    get_operation = app.openapi()["paths"]["/aris3/access-control/permission-catalog"]["get"]
    description = get_operation.get("description") or ""
    assert "Scoped permission catalog" in description
    assert "role templates" in description
    assert "overlays" in description
    assert "user overrides" in description


def test_admin_access_control_endpoints_are_consistently_documented():
    paths = app.openapi()["paths"]

    for path, methods in paths.items():
        if not path.startswith(ADMIN_ACCESS_CONTROL_PATH_PREFIX):
            continue
        for method, operation in methods.items():
            if method not in {"get", "put", "post", "patch", "delete"}:
                continue
            responses = operation.get("responses", {})
            success_schema = _response_schema(responses.get("200", {})) or _response_schema(responses.get("201", {}))
            assert success_schema is not None, f"{method.upper()} {path} is missing success response schema"
            assert "422" in responses, f"{method.upper()} {path} is missing 422 response"


def test_admin_error_response_shapes_expose_uniform_envelope_for_404_409_422():
    openapi = app.openapi()
    paths = openapi["paths"]

    for path, methods in paths.items():
        if not path.startswith("/aris3/admin"):
            continue
        for method, operation in methods.items():
            if method not in {"get", "put", "post", "patch", "delete"}:
                continue
            responses = operation.get("responses", {})
            for code, expected_ref in {
                "404": "#/components/schemas/NotFoundErrorResponse",
                "409": "#/components/schemas/ConflictErrorResponse",
                "422": "#/components/schemas/ValidationErrorResponse",
            }.items():
                if code not in responses:
                    continue
                schema = _response_schema(responses[code])
                assert schema == {"$ref": expected_ref}, f"{method.upper()} {path} {code} should use {expected_ref}"

    for component_name in ["NotFoundErrorResponse", "ConflictErrorResponse", "ValidationError"]:
        properties = openapi["components"]["schemas"][component_name]["properties"]
        assert {"code", "message", "details", "trace_id"}.issubset(properties.keys())
