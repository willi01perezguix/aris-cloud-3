from app.main import app


def test_transfers_openapi_required_example_keys_present() -> None:
    detail_examples = app.openapi()["paths"]["/aris3/transfers/{transfer_id}"]["get"]["responses"]["200"]["content"]["application/json"]["examples"]
    assert set(["draft", "dispatched", "received"]).issubset(detail_examples.keys())
    assert detail_examples["draft"]["summary"] == "Draft transfer detail"
    assert detail_examples["dispatched"]["summary"] == "Dispatched transfer detail"
    assert detail_examples["received"]["summary"] == "Received transfer detail"

    actions_req_examples = app.openapi()["paths"]["/aris3/transfers/{transfer_id}/actions"]["post"]["requestBody"]["content"]["application/json"]["examples"]
    assert set(["dispatch", "receive", "cancel"]).issubset(actions_req_examples.keys())
    assert actions_req_examples["dispatch"]["summary"] == "Dispatch action request"
    assert actions_req_examples["receive"]["summary"] == "Receive action request"
    assert actions_req_examples["cancel"]["summary"] == "Cancel action request"

    actions_resp_examples = app.openapi()["paths"]["/aris3/transfers/{transfer_id}/actions"]["post"]["responses"]["200"]["content"]["application/json"]["examples"]
    assert set(["dispatch", "receive", "cancel"]).issubset(actions_resp_examples.keys())
    assert actions_resp_examples["dispatch"]["summary"] == "Dispatch action response"
    assert actions_resp_examples["receive"]["summary"] == "Receive action response"
    assert actions_resp_examples["cancel"]["summary"] == "Cancel action response"
