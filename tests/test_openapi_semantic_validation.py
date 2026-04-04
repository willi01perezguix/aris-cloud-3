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


def test_release_artifact_is_semantically_valid():
    artifact = json.loads(Path("artifacts/release_candidate/openapi.json").read_text(encoding="utf-8"))
    assert_semantically_valid_openapi(artifact)
