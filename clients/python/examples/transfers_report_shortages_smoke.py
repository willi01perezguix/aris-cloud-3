from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.transfers_client import TransfersClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.stock_validation import ClientValidationError
from aris3_client_sdk.transfer_validation import validate_shortage_report_payload


def _load_payload(path: str | None) -> dict:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "shortages": [
            {"line_id": "line-id", "qty": 1, "reason_code": "MISSING", "notes": "Not in shipment"}
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS3 transfers report shortages smoke CLI")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--transfer-id", required=True)
    parser.add_argument("--input", help="Path to JSON file")
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = TransfersClient(http=session._http(), access_token=session.token)

    try:
        payload = _load_payload(args.input)
        validated = validate_shortage_report_payload(payload)
        keys = new_idempotency_keys()
        response = client.transfer_action(
            args.transfer_id,
            "report_shortages",
            validated,
            transaction_id=keys.transaction_id,
            idempotency_key=keys.idempotency_key,
        )
        print(json.dumps({"id": response.header.id, "status": response.header.status}, indent=2))
    except ClientValidationError as exc:
        print(json.dumps({"error": "validation", "issues": [issue.__dict__ for issue in exc.issues]}, indent=2))
        raise SystemExit(1) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "input", "message": str(exc)}, indent=2))
        raise SystemExit(1) from exc
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
