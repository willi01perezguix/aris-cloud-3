from __future__ import annotations

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.admin_data_access import AdminDataAccessClient
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


@responses.activate
def test_permission_catalog_and_effective_permissions(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    client = AdminDataAccessClient(http=http, access_token="token")

    responses.add(
        responses.GET,
        "https://api.example.com/aris3/admin/access-control/permission-catalog",
        json={"permissions": [{"code": "users.read", "description": "Read users"}], "trace_id": "trace"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/admin/access-control/effective-permissions",
        match=[responses.matchers.query_param_matcher({"user_id": "user-1", "store_id": "store-1"})],
        json={"user_id": "user-1", "permissions": [], "trace_id": "trace"},
        status=200,
    )

    catalog = client.get_permission_catalog()
    effective = client.get_effective_permissions("user-1", store_id="store-1")

    assert catalog["permissions"][0]["code"] == "users.read"
    assert effective["user_id"] == "user-1"


@responses.activate
def test_replace_role_template_sets_idempotency_headers(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    client = AdminDataAccessClient(http=http, access_token="token")

    responses.add(
        responses.PUT,
        "https://api.example.com/aris3/admin/access-control/role-templates/USER",
        match=[
            responses.matchers.header_matcher({"Idempotency-Key": "idem-1", "transaction_id": "tx-1"}),
            responses.matchers.json_params_matcher({"permissions": ["users.read"], "transaction_id": "tx-1"}),
        ],
        json={"role": "USER", "permissions": ["users.read"], "trace_id": "trace"},
        status=200,
    )

    result = client.replace_role_template(
        "USER",
        {"permissions": ["users.read"], "transaction_id": "tx-1"},
        idempotency_key="idem-1",
        transaction_id="tx-1",
    ).retry()

    assert result["role"] == "USER"


@responses.activate
def test_patch_return_policy_and_variant_fields(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    client = AdminDataAccessClient(http=http, access_token="token")

    responses.add(
        responses.PATCH,
        "https://api.example.com/aris3/admin/settings/return-policy",
        match=[responses.matchers.header_matcher({"Idempotency-Key": "idem-rp", "transaction_id": "tx-rp"})],
        json={"return_window_days": 30, "trace_id": "trace"},
        status=200,
    )
    responses.add(
        responses.PATCH,
        "https://api.example.com/aris3/admin/settings/variant-fields",
        match=[responses.matchers.header_matcher({"Idempotency-Key": "idem-vf", "transaction_id": "tx-vf"})],
        json={"var1_label": "Color", "var2_label": "Size", "trace_id": "trace"},
        status=200,
    )

    return_policy = client.patch_return_policy(
        {"return_window_days": 30, "transaction_id": "tx-rp"},
        idempotency_key="idem-rp",
        transaction_id="tx-rp",
    ).retry()
    variant_fields = client.patch_variant_fields(
        {"var1_label": "Color", "var2_label": "Size", "transaction_id": "tx-vf"},
        idempotency_key="idem-vf",
        transaction_id="tx-vf",
    ).retry()

    assert return_policy["return_window_days"] == 30
    assert variant_fields["var1_label"] == "Color"
