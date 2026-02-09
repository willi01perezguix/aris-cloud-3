from __future__ import annotations

import argparse
import json
import os

from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models_stock import StockQuery


def _default_int(env_key: str, fallback: int) -> int:
    raw = os.getenv(env_key)
    if raw is None:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def cmd_stock(args: argparse.Namespace) -> None:
    config = load_config(args.env_file)
    session = ApiSession(config)
    client = StockClient(http=session._http(), access_token=session.token)

    query = StockQuery(
        q=args.q,
        description=args.description,
        var1_value=args.var1_value,
        var2_value=args.var2_value,
        sku=args.sku,
        epc=args.epc,
        location_code=args.location_code,
        pool=args.pool,
        from_date=args.from_date,
        to_date=args.to_date,
        page=args.page,
        page_size=args.page_size,
        sort_by=args.sort_by,
        sort_order=args.sort_order,
    )

    response = client.get_stock(query)
    print(f"Environment: {config.env_name}")
    print(f"Base URL: {config.api_base_url}")
    meta = response.meta
    totals = response.totals
    print(
        "Meta: "
        f"page={meta.page} page_size={meta.page_size} "
        f"total_rows={totals.total_rows} sort_by={meta.sort_by} sort_dir={meta.sort_dir}"
    )
    print(
        "Totals: "
        f"rfid={totals.total_rfid} pending={totals.total_pending} units={totals.total_units}"
    )

    limit = args.limit
    rows = response.rows[:limit]
    print(f"Rows (showing {len(rows)} of {len(response.rows)}):")
    for row in rows:
        payload = row.model_dump(exclude_none=True, mode="json")
        compact = {key: payload.get(key) for key in ("sku", "epc", "description", "location_code", "pool", "status")}
        compact["id"] = payload.get("id")
        print(json.dumps(compact, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS3 stock smoke CLI")
    parser.add_argument("--env-file", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stock_parser = subparsers.add_parser("stock")
    stock_parser.add_argument("--q")
    stock_parser.add_argument("--description")
    stock_parser.add_argument("--var1-value")
    stock_parser.add_argument("--var2-value")
    stock_parser.add_argument("--sku")
    stock_parser.add_argument("--epc")
    stock_parser.add_argument("--location-code")
    stock_parser.add_argument("--pool")
    stock_parser.add_argument("--from", dest="from_date")
    stock_parser.add_argument("--to", dest="to_date")
    stock_parser.add_argument("--page", type=int, default=1)
    stock_parser.add_argument("--page-size", type=int, default=_default_int("ARIS3_DEFAULT_PAGE_SIZE", 50))
    stock_parser.add_argument("--sort-by", default=os.getenv("ARIS3_DEFAULT_SORT_BY", "created_at"))
    stock_parser.add_argument("--sort-order", default=os.getenv("ARIS3_DEFAULT_SORT_ORDER", "desc"))
    stock_parser.add_argument("--limit", type=int, default=5)
    stock_parser.set_defaults(func=cmd_stock)

    args = parser.parse_args()
    try:
        args.func(args)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
