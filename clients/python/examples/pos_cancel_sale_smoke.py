from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.pos_sales_client import PosSalesClient
from aris3_client_sdk.exceptions import ApiError


def main() -> None:
    parser = argparse.ArgumentParser(description="Cancel a POS sale (smoke)")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--sale-id", required=True)
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = PosSalesClient(http=session._http(), access_token=session.token)
    keys = new_idempotency_keys()
    payload = {"transaction_id": keys.transaction_id, "action": "cancel"}

    try:
        response = client.sale_action(args.sale_id, "cancel", payload, idempotency_key=keys.idempotency_key)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc

    print(f"Sale canceled: {response.header.id} status={response.header.status}")


if __name__ == "__main__":
    main()
