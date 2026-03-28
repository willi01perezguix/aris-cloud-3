from app.main import app


def test_openapi_pos_returns_examples_are_endpoint_specific():
    paths = app.openapi()["paths"]

    eligibility = paths["/aris3/pos/returns/eligibility"]["get"]["responses"]
    assert eligibility["404"]["content"]["application/json"]["example"]["message"] == "sale not found"

    get_return = paths["/aris3/pos/returns/{return_id}"]["get"]["responses"]
    assert "409" not in get_return


def test_openapi_pos_cash_has_coherent_409_example():
    responses = app.openapi()["paths"]["/aris3/pos/cash/session/actions"]["post"]["responses"]
    conflict = responses["409"]["content"]["application/json"]["example"]
    assert conflict["message"] == "cash session already open"


def test_openapi_admin_query_tenant_legacy_docs_and_status_description_canonical():
    openapi = app.openapi()
    stores_post = openapi["paths"]["/aris3/admin/stores"]["post"]

    assert "query_tenant_id" in (stores_post.get("description") or "")
    body_examples = stores_post["requestBody"]["content"]["application/json"].get("examples", {})
    assert "legacy_query_tenant" not in body_examples

    tenant_status_desc = openapi["components"]["schemas"]["TenantActionRequest"]["properties"]["status"]["description"]
    assert "Lowercase variants are accepted" not in tenant_status_desc
