from app.main import app


def test_tenant_role_policy_docs_explain_jwt_scope():
    get_op = app.openapi()["paths"]["/aris3/admin/access-control/tenant-role-policies/{role_name}"]["get"]
    put_op = app.openapi()["paths"]["/aris3/admin/access-control/tenant-role-policies/{role_name}"]["put"]

    assert "JWT/context" in (get_op.get("description") or "")
    assert "JWT/context" in (put_op.get("description") or "")


def test_user_actions_schema_documents_conditional_fields():
    op = app.openapi()["paths"]["/aris3/admin/users/{user_id}/actions"]["post"]
    schema_ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = schema_ref.rsplit("/", 1)[-1]
    schema = app.openapi()["components"]["schemas"][schema_name]
    properties = schema["properties"]

    assert sorted(properties["action"]["enum"]) == ["reset_password", "set_role", "set_status"]
    assert "set_status" in properties["status"]["description"]
    assert "set_role" in properties["role"]["description"]
    assert "reset_password" in properties["temporary_password"]["description"]


def test_admin_error_responses_are_documented_with_trace_id_schema():
    op = app.openapi()["paths"]["/aris3/admin/settings/variant-fields"]["patch"]
    responses = op["responses"]

    assert "404" in responses
    assert "409" in responses
    assert "422" in responses

    openapi = app.openapi()
    error_ref = responses["404"]["content"]["application/json"]["schema"]["$ref"]
    error_schema = openapi["components"]["schemas"][error_ref.rsplit("/", 1)[-1]]
    assert "trace_id" in error_schema["properties"]
