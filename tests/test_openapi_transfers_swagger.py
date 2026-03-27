from app.main import app


def _assert_qty_consistency(transfer_example: dict) -> None:
    for line in transfer_example["lines"]:
        assert line["outstanding_qty"] == line["qty"] - line["received_qty"]


def test_transfers_create_and_update_examples_are_draft() -> None:
    openapi = app.openapi()["paths"]

    create_example = openapi["/aris3/transfers"]["post"]["responses"]["201"]["content"]["application/json"]["example"]
    patch_example = openapi["/aris3/transfers/{transfer_id}"]["patch"]["responses"]["200"]["content"]["application/json"]["example"]

    for example in (create_example, patch_example):
        assert example["header"]["status"] == "DRAFT"
        assert "dispatched_at" not in example["header"]
        assert "dispatched_by_user_id" not in example["header"]
        assert "received_at" not in example["header"]
        assert "canceled_at" not in example["header"]
        assert example["movement_summary"]["dispatched_lines"] == 0
        assert example["movement_summary"]["dispatched_qty"] == 0
        assert example["movement_summary"]["pending_reception"] is True
        assert example["movement_summary"]["shortages_possible"] is True
        _assert_qty_consistency(example)


def test_transfers_list_and_detail_examples_cover_expected_states() -> None:
    openapi = app.openapi()["paths"]

    list_example = openapi["/aris3/transfers"]["get"]["responses"]["200"]["content"]["application/json"]["example"]["rows"][0]
    detail_examples = openapi["/aris3/transfers/{transfer_id}"]["get"]["responses"]["200"]["content"]["application/json"]["examples"]

    assert list_example["header"]["status"] == "DISPATCHED"
    assert list_example["movement_summary"]["dispatched_lines"] == 1
    assert list_example["movement_summary"]["dispatched_qty"] == 1
    _assert_qty_consistency(list_example)

    assert "draft" in detail_examples
    assert "dispatched" in detail_examples
    assert "received" in detail_examples
    assert detail_examples["draft"]["value"]["header"]["status"] == "DRAFT"
    assert detail_examples["draft"]["value"]["lines"][0]["qty"] == 1
    assert detail_examples["draft"]["value"]["lines"][0]["received_qty"] == 0
    assert detail_examples["draft"]["value"]["lines"][0]["outstanding_qty"] == 1
    assert detail_examples["draft"]["value"]["movement_summary"]["dispatched_lines"] == 0
    assert detail_examples["draft"]["value"]["movement_summary"]["dispatched_qty"] == 0
    assert detail_examples["dispatched"]["value"]["header"]["status"] == "DISPATCHED"
    assert detail_examples["dispatched"]["value"]["header"]["dispatched_at"] is not None
    assert detail_examples["dispatched"]["value"]["lines"][0]["qty"] == 1
    assert detail_examples["dispatched"]["value"]["lines"][0]["received_qty"] == 0
    assert detail_examples["dispatched"]["value"]["lines"][0]["outstanding_qty"] == 1
    assert detail_examples["dispatched"]["value"]["movement_summary"]["dispatched_lines"] == 1
    assert detail_examples["dispatched"]["value"]["movement_summary"]["dispatched_qty"] == 1
    assert detail_examples["dispatched"]["value"]["movement_summary"]["pending_reception"] is True
    assert detail_examples["received"]["value"]["header"]["status"] == "RECEIVED"
    assert detail_examples["received"]["value"]["header"]["dispatched_at"] is not None
    assert detail_examples["received"]["value"]["header"]["received_at"] is not None
    assert detail_examples["received"]["value"]["lines"][0]["qty"] == 1
    assert detail_examples["received"]["value"]["lines"][0]["received_qty"] == 1
    assert detail_examples["received"]["value"]["lines"][0]["outstanding_qty"] == 0
    assert detail_examples["received"]["value"]["movement_summary"]["pending_reception"] is False


def test_transfers_actions_examples_and_errors_are_documented() -> None:
    actions_op = app.openapi()["paths"]["/aris3/transfers/{transfer_id}/actions"]["post"]

    request_examples = actions_op["requestBody"]["content"]["application/json"]["examples"]
    assert request_examples["dispatch"]["value"] == {"action": "dispatch", "transaction_id": "txn-dispatch-1"}
    assert request_examples["receive"]["value"] == {
        "action": "receive",
        "transaction_id": "txn-receive-1",
        "receive_lines": [
            {
                "line_id": "33333333-3333-3333-3333-333333333333",
                "qty": 1,
                "location_code": "ONLINE-A1",
                "pool": "VENTA",
                "location_is_vendible": True,
            }
        ],
    }
    assert request_examples["cancel"]["value"] == {"action": "cancel", "transaction_id": "txn-cancel-1"}
    assert set(actions_op["responses"]["200"]["content"]["application/json"]["examples"].keys()) >= {
        "dispatch",
        "receive",
        "cancel",
    }
    response_examples = actions_op["responses"]["200"]["content"]["application/json"]["examples"]
    assert response_examples["dispatch"]["value"]["header"]["status"] == "DISPATCHED"
    assert response_examples["receive"]["value"]["header"]["status"] == "RECEIVED"
    assert response_examples["cancel"]["value"]["header"]["status"] == "CANCELED"

    assert "examples" in actions_op["responses"]["409"]["content"]["application/json"]
    assert "examples" in actions_op["responses"]["422"]["content"]["application/json"]
    error_examples = actions_op["responses"]["422"]["content"]["application/json"]["examples"]
    assert "dispatch_invalid_state" in error_examples
    assert "receive_invalid_state" in error_examples
    assert "cancel_invalid_state" in error_examples


def test_transfers_line_type_schema_is_epc_only() -> None:
    openapi = app.openapi()
    schema = openapi["components"]["schemas"]["TransferLineCreate"]
    assert schema["properties"]["line_type"]["const"] == "EPC"
    create_example = openapi["components"]["schemas"]["TransferCreateRequest"]["example"]
    update_example = openapi["components"]["schemas"]["TransferUpdateRequest"]["example"]
    assert create_example["lines"][0]["line_type"] == "EPC"
    assert update_example["lines"][0]["line_type"] == "EPC"
