from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.inventory_counts_client import InventoryCountsClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.inventory_counts_validation import (
    ClientValidationError,
    validate_action_state_intent,
    validate_reconcile_payload,
    validate_scan_batch_payload,
    validate_start_payload,
)


def _print_error(exc: ApiError) -> None:
    print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--store-id", default="")
    parser.add_argument("--count-id", default="")
    parser.add_argument("--epc", default="")
    parser.add_argument("--sku", default="")
    parser.add_argument("--qty", type=int, default=1)
    args = parser.parse_args()

    name = __file__.split("/")[-1]
    cfg = load_config(args.env_file)
    session = ApiSession(cfg)
    client = InventoryCountsClient(http=session._http(), access_token=session.token)

    try:
        if name == "inv_count_start_smoke.py":
            payload = validate_start_payload({"store_id": args.store_id})
            keys = new_idempotency_keys()
            res = client.create_or_start_count(payload, transaction_id=keys.transaction_id, idempotency_key=keys.idempotency_key)
            print(json.dumps({"id": res.id, "state": res.state}, indent=2))
        elif name == "inv_count_scan_batch_smoke.py":
            payload = validate_scan_batch_payload({"items": [{"epc": args.epc, "sku": args.sku, "qty": args.qty}]})
            keys = new_idempotency_keys()
            res = client.submit_scan_batch(args.count_id, payload, transaction_id=keys.transaction_id, idempotency_key=keys.idempotency_key)
            print(json.dumps(res.model_dump(mode="json"), indent=2))
        elif name == "inv_count_pause_resume_smoke.py":
            header = client.get_count(args.count_id)
            action = "PAUSE" if header.state.upper() == "ACTIVE" else "RESUME"
            validate_action_state_intent(header.state, action)
            keys = new_idempotency_keys()
            res = client.count_action(args.count_id, action, {"action": action}, transaction_id=keys.transaction_id, idempotency_key=keys.idempotency_key, current_state=header.state)
            print(json.dumps({"id": res.id, "state": res.state, "action": action}, indent=2))
        elif name == "inv_count_close_smoke.py":
            header = client.get_count(args.count_id)
            validate_action_state_intent(header.state, "CLOSE")
            keys = new_idempotency_keys()
            res = client.count_action(args.count_id, "CLOSE", {"action": "CLOSE"}, transaction_id=keys.transaction_id, idempotency_key=keys.idempotency_key, current_state=header.state)
            print(json.dumps({"id": res.id, "state": res.state}, indent=2))
        elif name == "inv_count_reconcile_smoke.py":
            payload = validate_reconcile_payload({})
            keys = new_idempotency_keys()
            res = client.reconcile_count(args.count_id, payload, transaction_id=keys.transaction_id, idempotency_key=keys.idempotency_key)
            print(json.dumps(res.model_dump(mode="json"), indent=2))
        elif name == "inv_count_summary_diff_smoke.py":
            summary = client.get_count_summary(args.count_id)
            diffs = client.get_count_differences(args.count_id)
            print(json.dumps({"summary": summary.model_dump(mode="json"), "differences": diffs.model_dump(mode="json")}, indent=2))
        elif name == "inv_count_export_smoke.py":
            data = client.export_count_result(args.count_id, export_format="csv")
            if data is None:
                print("not available in contract")
                return
            print(json.dumps(data.model_dump(mode="json"), indent=2))
    except ClientValidationError as exc:
        print(json.dumps({"error": "validation", "issues": [issue.__dict__ for issue in exc.issues]}, indent=2))
        raise SystemExit(1) from exc
    except ApiError as exc:
        _print_error(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
