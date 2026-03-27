from app.main import app


def test_transfers_openapi_required_example_keys_present() -> None:
    paths = app.openapi()["paths"]

    detail_examples = paths["/aris3/transfers/{transfer_id}"]["get"]["responses"]["200"]["content"]["application/json"]["examples"]
    assert {"draft", "dispatched", "received"}.issubset(detail_examples.keys())

    actions_post = paths["/aris3/transfers/{transfer_id}/actions"]["post"]

    request_examples = actions_post["requestBody"]["content"]["application/json"]["examples"]
    assert {"dispatch", "receive", "cancel"}.issubset(request_examples.keys())

    response_examples = actions_post["responses"]["200"]["content"]["application/json"]["examples"]
    assert {"dispatch", "receive", "cancel"}.issubset(response_examples.keys())
