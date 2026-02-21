from app.main import app


def test_openapi_admin_list_filters_documented():
    spec = app.openapi()["paths"]

    users_params = {item["name"] for item in spec["/aris3/admin/users"]["get"]["parameters"]}
    stores_params = {item["name"] for item in spec["/aris3/admin/stores"]["get"]["parameters"]}
    tenants_params = {item["name"] for item in spec["/aris3/admin/tenants"]["get"]["parameters"]}

    assert {"tenant_id", "store_id", "role", "status", "search", "limit", "offset"}.issubset(users_params)
    assert {"tenant_id", "search", "limit", "offset"}.issubset(stores_params)
    assert {"status", "search", "limit", "offset"}.issubset(tenants_params)
