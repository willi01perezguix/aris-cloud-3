from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.media_client import MediaClient
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models_stock import StockQuery


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize stock media fallback sources")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--page-size", type=int, default=50)
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    stock = StockClient(http=session._http(), access_token=session.token)
    media = MediaClient(http=session._http(), access_token=session.token)
    try:
        rows = stock.get_stock(StockQuery(page=1, page_size=args.page_size)).rows
        counts = {"VARIANT": 0, "SKU": 0, "PLACEHOLDER": 0}
        for row in rows:
            resolved = media.resolve_for_variant(row.sku or "", row.var1_value, row.var2_value)
            counts[resolved.source] = counts.get(resolved.source, 0) + 1
        print(json.dumps({"rows": len(rows), "counts": counts}, indent=2))
    except ApiError as exc:
        print(json.dumps({"code": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
