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
    assert is_active_param["description"] == "Deprecated compatibility filter derived from status (ACTIVE=true, others=false)."


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
    assert paths["/aris3/admin/tenants/{tenant_id}/purge"]["post"]["summary"] == "Purge tenant"
    assert paths["/aris3/admin/stores/{store_id}/purge"]["post"]["summary"] == "Purge store"
    assert paths["/aris3/admin/users/{user_id}/purge"]["post"]["summary"] == "Purge user"


def test_tenant_purge_openapi_contract_describes_safe_delete_vs_purge():
    operation = app.openapi()["paths"]["/aris3/admin/tenants/{tenant_id}/purge"]["post"]
    description = operation.get("description") or ""
    assert "Destructive hard-delete workflow" in description
    assert "safe delete" in description
    assert operation["requestBody"]["required"] is True
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/TenantPurgeResponse"


def test_store_and_user_purge_openapi_contract_describes_safe_delete_and_special_behavior():
    openapi = app.openapi()
    paths = openapi["paths"]

    store_operation = paths["/aris3/admin/stores/{store_id}/purge"]["post"]
    store_description = store_operation.get("description") or ""
    assert "Destructive hard-delete workflow" in store_description
    assert "safe delete" in store_description

    user_operation = paths["/aris3/admin/users/{user_id}/purge"]["post"]
    user_description = user_operation.get("description") or ""
    assert "Transfer actor references are safely nullified" in user_description
    assert "safe delete" in user_description

    store_counts_schema_ref = openapi["components"]["schemas"]["StorePurgeCounts"]
    expected_store_count_keys = {
        "transfer_movements",
        "transfer_lines",
        "users",
        "user_permission_overrides",
        "sale_lines",
        "payments",
        "transfers",
        "sales",
        "returns",
        "cash_sessions",
        "cash_movements",
        "cash_day_closes",
        "exports",
        "store_role_policies",
        "stock_items",
        "stores",
    }
    assert expected_store_count_keys.issubset(set(store_counts_schema_ref["properties"].keys()))


def test_self_permission_catalog_description_is_clear_and_canonical():
    get_operation = app.openapi()["paths"]["/aris3/access-control/permission-catalog"]["get"]
    description = get_operation.get("description") or ""
    assert "Self-context permission catalog" in description
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


def test_public_access_control_surface_only_exposes_self_endpoints():
    paths = app.openapi()["paths"]

    assert "/aris3/access-control/effective-permissions" in paths
    assert "/aris3/access-control/permission-catalog" in paths

    hidden_public_paths = [
        "/aris3/access-control/effective-permissions/users/{user_id}",
        "/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/users/{user_id}/effective-permissions",
        "/aris3/access-control/tenants/{tenant_id}/role-policies/{role_name}",
        "/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/role-policies/{role_name}",
        "/aris3/access-control/tenants/{tenant_id}/users/{user_id}/permission-overrides",
        "/aris3/access-control/platform/role-policies/{role_name}",
    ]
    for path in hidden_public_paths:
        assert path not in paths




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


def test_auth_token_and_change_password_docs_clarify_canonical_contract():
    paths = app.openapi()["paths"]

    login_post = paths["/aris3/auth/login"]["post"]
    token_post = paths["/aris3/auth/token"]["post"]
    patch_change_password = paths["/aris3/auth/change-password"]["patch"]
    post_change_password = paths["/aris3/auth/change-password"]["post"]

    assert "Canonical authentication endpoint" in (login_post.get("description") or "")
    assert token_post.get("deprecated") is True
    assert "compatibility" in (token_post.get("summary") or "").lower()
    assert "POST /aris3/auth/login" in (token_post.get("description") or "")
    assert post_change_password.get("deprecated") is True
    assert patch_change_password.get("deprecated") is not True


def test_transfers_tenant_id_query_param_is_deprecated_with_clear_guidance():
    get_operation = app.openapi()["paths"]["/aris3/transfers"]["get"]
    params = {param["name"]: param for param in get_operation.get("parameters", [])}

    assert "tenant_id" in params
    assert params["tenant_id"].get("deprecated") is True
    assert "Deprecated compatibility tenant scope filter" in (params["tenant_id"].get("description") or "")


def test_ops_metrics_endpoint_is_documented_as_internal_operations_surface():
    get_operation = app.openapi()["paths"]["/aris3/ops/metrics"]["get"]
    assert "internal" in (get_operation.get("summary") or "").lower()
    assert "Not a product workflow endpoint" in (get_operation.get("description") or "")


def test_stock_actions_and_admin_access_control_are_documented_with_admin_operations_persona():
    openapi = app.openapi()
    stock_actions = openapi["paths"]["/aris3/stock/actions"]["post"]
    assert "operations workflow" in (stock_actions.get("summary") or "").lower()
    assert "Not intended as a generic public catalog" in (stock_actions.get("description") or "")

    acl_effective = openapi["paths"]["/aris3/admin/access-control/effective-permissions"]["get"]
    assert "Administrative/internal access-control endpoint" in (acl_effective.get("description") or "")


def test_error_code_guidance_documents_canonical_and_compatibility_vocab():
    code_schema = app.openapi()["components"]["schemas"]["ApiError"]["properties"]["code"]
    description = code_schema.get("description") or ""

    assert "INVALID_TOKEN" in description
    assert "PERMISSION_DENIED" in description
    assert "RESOURCE_NOT_FOUND" in description
    assert "CONFLICT" in description
    assert "VALIDATION_ERROR" in description
    assert "Compatibility aliases" in description
    assert "UNAUTHORIZED" in description
    assert "FORBIDDEN" in description
    assert "NOT_FOUND" in description
    assert "BUSINESS_CONFLICT" in description


def test_admin_stores_list_query_tenant_id_is_explicitly_deprecated_alias():
    get_operation = app.openapi()["paths"]["/aris3/admin/stores"]["get"]
    params = {param["name"]: param for param in get_operation.get("parameters", [])}

    assert "query_tenant_id" in params
    legacy_param = params["query_tenant_id"]
    assert legacy_param.get("deprecated") is True
    assert "Deprecated alias for tenant_id" in (legacy_param.get("description") or "")


def test_ready_openapi_documents_503_database_unavailable_contract():
    get_operation = app.openapi()["paths"]["/ready"]["get"]
    response_503 = get_operation["responses"]["503"]
    schema = _response_schema(response_503)

    assert "Dependency unavailable" in (response_503.get("description") or "")
    assert schema == {"$ref": "#/components/schemas/ApiErrorResponse"}


def test_variant_fields_endpoint_is_persona_labeled_as_admin_internal_surface():
    paths = app.openapi()["paths"]
    get_operation = paths["/aris3/admin/settings/variant-fields"]["get"]
    patch_operation = paths["/aris3/admin/settings/variant-fields"]["patch"]

    assert "Administrative/internal settings endpoint" in (get_operation.get("description") or "")
    assert "Administrative/internal settings endpoint" in (patch_operation.get("description") or "")
