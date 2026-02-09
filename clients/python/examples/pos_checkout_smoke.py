from __future__ import annotations

import argparse
import json
from decimal import Decimal

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.pos_cash_client import PosCashClient
from aris3_client_sdk.clients.pos_sales_client import PosSalesClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.payment_validation import validate_checkout_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Checkout a POS sale (smoke)")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--sale-id", required=True)
    parser.add_argument("--cash", type=float, default=0.0)
    parser.add_argument("--card", type=float, default=0.0)
    parser.add_argument("--card-auth")
    parser.add_argument("--transfer", type=float, default=0.0)
    parser.add_argument("--bank-name")
    parser.add_argument("--voucher-number")
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = PosSalesClient(http=session._http(), access_token=session.token)

    try:
        sale = client.get_sale(args.sale_id)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc

    payments: list[dict] = []
    if args.cash > 0:
        payments.append({"method": "CASH", "amount": args.cash})
    if args.card > 0:
        payments.append({"method": "CARD", "amount": args.card, "authorization_code": args.card_auth})
    if args.transfer > 0:
        payments.append(
            {
                "method": "TRANSFER",
                "amount": args.transfer,
                "bank_name": args.bank_name,
                "voucher_number": args.voucher_number,
            }
        )

    validation = validate_checkout_payload(total_due=Decimal(str(sale.header.total_due)), payments=payments)
    if not validation.ok:
        print("Validation errors:")
        for issue in validation.issues:
            print(f"- {issue.field}: {issue.reason}")
        raise SystemExit(1)

    if validation.totals.cash_total > 0:
        cash_client = PosCashClient(http=session._http(), access_token=session.token)
        current = cash_client.get_current_session(store_id=sale.header.store_id)
        if current.session is None:
            print("CASH checkout requires an open cash session.")
            raise SystemExit(1)

    keys = new_idempotency_keys()
    payload = {
        "transaction_id": keys.transaction_id,
        "action": "checkout",
        "payments": payments,
    }

    try:
        response = client.sale_action(args.sale_id, "checkout", payload, idempotency_key=keys.idempotency_key)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc

    print(
        "Checkout complete: "
        f"status={response.header.status} paid_total={response.header.paid_total} "
        f"change_due={response.header.change_due}"
    )


if __name__ == "__main__":
    main()
