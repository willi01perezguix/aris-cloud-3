from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.reports_client import ReportsClient
from aris3_client_sdk.exceptions import ApiError


def main() -> None:
    parser = argparse.ArgumentParser(description="Reports overview smoke")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--store-id")
    parser.add_argument("--from-date", dest="from_value")
    parser.add_argument("--to-date", dest="to_value")
    parser.add_argument("--timezone", default="UTC")
    args = parser.parse_args()
    try:
        session = ApiSession(load_config(args.env_file))
        client = ReportsClient(http=session._http(), access_token=session.token)
        response = client.get_sales_overview({"store_id": args.store_id, "from": args.from_value, "to": args.to_value, "timezone": args.timezone})
        t = response.totals
        print(json.dumps({"net_sales": str(t.net_sales), "gross_sales": str(t.gross_sales), "returns": str(t.refunds_total), "orders": t.orders_paid_count, "avg_ticket": str(t.average_ticket), "trace_id": response.meta.trace_id}, indent=2))
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
