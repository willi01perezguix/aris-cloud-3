from app.main import app


def test_access_control_paths_are_tagged_by_scope_and_admin_alias_deprecated():
    openapi = app.openapi()["paths"]

    scoped_op = openapi["/aris3/access-control/tenants/{tenant_id}/role-policies/{role_name}"]["get"]
    admin_op = openapi["/aris3/admin/access-control/tenant-role-policies/{role_name}"]["get"]
    alias_op = openapi["/aris3/admin/access-control/permission-catalog"]["get"]

    assert scoped_op["tags"] == ["Access Control Scoped"]
    assert admin_op["tags"] == ["Admin Access Control"]
    assert alias_op.get("deprecated") is True


def test_admin_and_access_control_422_use_validation_envelope_component():
    openapi = app.openapi()
    paths = openapi["paths"]

    admin_422 = paths["/aris3/admin/users"]["post"]["responses"]["422"]
    scoped_422 = paths["/aris3/access-control/effective-permissions/users/{user_id}"]["get"]["responses"]["422"]

    admin_ref = admin_422["content"]["application/json"]["schema"]["$ref"]
    scoped_ref = scoped_422["content"]["application/json"]["schema"]["$ref"]

    assert admin_ref == "#/components/schemas/ValidationErrorResponse"
    assert scoped_ref == "#/components/schemas/ValidationErrorResponse"


def test_admin_user_create_and_lists_document_filters_sort_and_pagination():
    openapi = app.openapi()["paths"]

    user_create = openapi["/aris3/admin/users"]["post"]
    assert "requestBody" in user_create
    assert all(code in user_create["responses"] for code in ["201", "404", "409", "422"])

    tenants_params = {item["name"] for item in openapi["/aris3/admin/tenants"]["get"]["parameters"]}
    stores_params = {item["name"] for item in openapi["/aris3/admin/stores"]["get"]["parameters"]}
    users_params = {item["name"] for item in openapi["/aris3/admin/users"]["get"]["parameters"]}

    assert {"status", "search", "limit", "offset", "sort_by", "sort_order"}.issubset(tenants_params)
    assert {"tenant_id", "search", "limit", "offset", "sort_by", "sort_order"}.issubset(stores_params)
    assert {"tenant_id", "store_id", "role", "status", "is_active", "search", "limit", "offset", "sort_by", "sort_order"}.issubset(users_params)
