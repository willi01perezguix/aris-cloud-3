from app.main import app


def test_tenant_role_policy_docs_explain_jwt_scope():
    get_op = app.openapi()["paths"]["/aris3/admin/access-control/tenant-role-policies/{role_name}"]["get"]
    put_op = app.openapi()["paths"]["/aris3/admin/access-control/tenant-role-policies/{role_name}"]["put"]

    assert "JWT/context" in (get_op.get("description") or "")
    assert "JWT/context" in (put_op.get("description") or "")


def test_user_actions_schema_uses_one_of_variants_with_examples():
    op = app.openapi()["paths"]["/aris3/admin/users/{user_id}/actions"]["post"]
    content = op["requestBody"]["content"]["application/json"]

    assert "oneOf" in content["schema"]
    assert len(content["schema"]["oneOf"]) == 3
    assert "set_status" in content["examples"]
    assert "set_role" in content["examples"]
    assert "reset_password" in content["examples"]


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


def test_effective_permissions_has_reusable_typed_enums():
    openapi = app.openapi()
    schema = openapi["components"]["schemas"]["EffectivePermissionsResponse"]

    role_schema = schema["properties"]["role"]["anyOf"][0]
    assert sorted(role_schema["enum"]) == ["ADMIN", "MANAGER", "PLATFORM_ADMIN", "SUPERADMIN", "USER"]

    item_ref = schema["properties"]["permissions"]["items"]["$ref"]
    item_schema = openapi["components"]["schemas"][item_ref.rsplit("/", 1)[-1]]
    assert "source" in item_schema["properties"]
    assert "enum" in item_schema["properties"]["source"]


def test_return_policy_strategy_exposes_enum_and_description():
    openapi = app.openapi()
    schema = openapi["components"]["schemas"]["ReturnPolicySettingsResponse"]
    strategy = schema["properties"]["non_reusable_label_strategy"]

    assert strategy["enum"] == ["ASSIGN_NEW_EPC", "TO_PENDING"]
    assert "Strategy for non-reusable labels" in strategy["description"]
