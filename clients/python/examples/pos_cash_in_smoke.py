from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.pos_cash_client import PosCashClient
from aris3_client_sdk.exceptions import ApiError


def main() -> None:
    parser = argparse.ArgumentParser(description="Cash in for POS cash session (smoke)")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--store-id", required=True)
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument("--reason")
    parser.add_argument("--tenant-id")
    parser.add_argument("--cashier-user-id")
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = PosCashClient(http=session._http(), access_token=session.token)
    keys = new_idempotency_keys()
    payload = {
        "transaction_id": keys.transaction_id,
        "tenant_id": args.tenant_id,
        "store_id": args.store_id,
        "action": "CASH_IN",
        "amount": args.amount,
        "reason": args.reason,
    }

    try:
        response = client.cash_action("CASH_IN", payload, idempotency_key=keys.idempotency_key)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc

    print(f"Cash in recorded: {response.id} expected_cash={response.expected_cash}")
    if args.cashier_user_id:
        current = client.get_current_session(store_id=args.store_id, cashier_user_id=args.cashier_user_id)
        print(f"Current session: {current.session.id if current.session else 'NONE'}")


if __name__ == "__main__":
    main()
