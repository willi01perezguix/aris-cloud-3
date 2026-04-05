import json
from pathlib import Path

from app.main import create_app
from app.aris3.openapi_validation import (
    assert_semantically_valid_openapi,
    find_unresolved_openapi_refs,
)


def test_runtime_openapi_has_no_unresolved_refs():
    spec = create_app().openapi()
    assert_semantically_valid_openapi(spec)


def test_semantic_validator_detects_missing_component_ref():
    spec = create_app().openapi()
    broken = json.loads(json.dumps(spec))
    del broken["components"]["schemas"]["PosSaleCreateRequest"]

    errors = find_unresolved_openapi_refs(broken)
    assert any("PosSaleCreateRequest" in err for err in errors)


def test_sales_actions_request_body_is_resolvable_and_swagger_safe():
    spec = create_app().openapi()
    body_schema = spec["paths"]["/aris3/pos/sales/{sale_id}/actions"]["post"]["requestBody"]["content"]["application/json"]["schema"]

    assert "$ref" not in body_schema
    assert body_schema["discriminator"]["propertyName"] == "action"
    assert set(body_schema["discriminator"]["mapping"].keys()) == {
        "CHECKOUT",
        "CANCEL",
        "REFUND_ITEMS",
        "EXCHANGE_ITEMS",
    }


def test_action_request_schemas_for_sales_transfers_returns_and_cash_are_resolvable():
    spec = create_app().openapi()
    action_operations = [
        ("/aris3/pos/sales/{sale_id}/actions", "post"),
        ("/aris3/transfers/{transfer_id}/actions", "post"),
        ("/aris3/pos/returns/{return_id}/actions", "post"),
        ("/aris3/pos/cash/session/actions", "post"),
        ("/aris3/pos/cash/day-close/actions", "post"),
    ]

    for path, method in action_operations:
        body_schema = spec["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
        body_ref = body_schema.get("$ref")
        if body_ref:
            assert body_ref.startswith("#/components/schemas/"), f"{method.upper()} {path} request body has non-local $ref"
            schema_name = body_ref.rsplit("/", 1)[-1]
            assert schema_name in spec["components"]["schemas"], f"{method.upper()} {path} request body points to missing schema `{schema_name}`"
            resolved = spec["components"]["schemas"][schema_name]
            has_union = bool(resolved.get("oneOf"))
            has_action_discriminator = isinstance(resolved.get("properties", {}).get("action"), dict)
            assert has_union or has_action_discriminator, (
                f"{method.upper()} {path} request body must keep action-specific contract"
            )
            continue
        assert body_schema.get("oneOf"), f"{method.upper()} {path} request body must keep action-discriminated contract"


def test_release_artifact_is_semantically_valid():
    artifact = json.loads(Path("artifacts/release_candidate/openapi.json").read_text(encoding="utf-8"))
    assert_semantically_valid_openapi(artifact)


def test_action_discriminator_mappings_resolve_local_components_for_pos_actions():
    spec = create_app().openapi()
    components = spec["components"]["schemas"]

    action_operations = [
        ("/aris3/pos/sales/{sale_id}/actions", "post"),
        ("/aris3/pos/returns/{return_id}/actions", "post"),
        ("/aris3/pos/cash/session/actions", "post"),
    ]

    for path, method in action_operations:
        body_schema = spec["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]
        discriminator = body_schema.get("discriminator") or {}
        mapping = discriminator.get("mapping") or {}
        assert mapping, f"{method.upper()} {path} discriminator mapping should not be empty"
        for action, ref in mapping.items():
            assert action.upper() == action
            assert ref.startswith("#/components/schemas/")
            schema_name = ref.rsplit("/", 1)[-1]
            assert schema_name in components
