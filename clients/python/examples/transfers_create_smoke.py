from __future__ import annotations

import argparse
import json
import os

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.transfers_client import TransfersClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.stock_validation import ClientValidationError
from aris3_client_sdk.transfer_validation import validate_create_transfer_payload


def _load_payload(path: str | None, origin_store_id: str | None, destination_store_id: str | None) -> dict:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    if not origin_store_id or not destination_store_id:
        raise ValueError("origin_store_id and destination_store_id are required when no input file is provided")
    return {
        "origin_store_id": origin_store_id,
        "destination_store_id": destination_store_id,
        "lines": [
            {
                "line_type": "SKU",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-1",
                    "description": "Sample",
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "location_is_vendible": True,
                },
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS3 transfers create smoke CLI")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--input", help="Path to JSON file")
    parser.add_argument("--origin-store-id", default=os.getenv("ARIS3_TRANSFER_ORIGIN_STORE_ID"))
    parser.add_argument("--destination-store-id", default=os.getenv("ARIS3_TRANSFER_DESTINATION_STORE_ID"))
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = TransfersClient(http=session._http(), access_token=session.token)

    try:
        payload = _load_payload(args.input, args.origin_store_id, args.destination_store_id)
        validated = validate_create_transfer_payload(payload)
        keys = new_idempotency_keys()
        response = client.create_transfer(
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
