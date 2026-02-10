from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.transfers_client import TransfersClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.stock_validation import ClientValidationError
from aris3_client_sdk.transfer_validation import validate_cancel_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS3 transfers cancel smoke CLI")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--transfer-id", required=True)
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = TransfersClient(http=session._http(), access_token=session.token)

    try:
        payload = validate_cancel_payload({})
        keys = new_idempotency_keys()
        response = client.transfer_action(
            args.transfer_id,
            "cancel",
            payload,
            transaction_id=keys.transaction_id,
            idempotency_key=keys.idempotency_key,
        )
        print(json.dumps({"id": response.header.id, "status": response.header.status}, indent=2))
    except ClientValidationError as exc:
        print(json.dumps({"error": "validation", "issues": [issue.__dict__ for issue in exc.issues]}, indent=2))
        raise SystemExit(1) from exc
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
