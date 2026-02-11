from __future__ import annotations

from aris3_client_sdk import ApiSession, AuthError, MustChangePasswordError, load_config
from aris3_client_sdk.models_stock import StockImportSkuLine, StockQuery


"""Quickstart for app teams:
1) configure env (ARIS3_API_BASE_URL, credentials)
2) login + me
3) stock full-table query
4) idempotent mutation helper
5) structured error handling
"""


def main() -> None:
    config = load_config()
    session = ApiSession(config=config)

    auth = session.auth_client()
    try:
        token = auth.login("demo@example.com", "change-me")
    except MustChangePasswordError as exc:
        print(f"Password reset required. trace={exc.trace_id}")
        return
    except AuthError as exc:
        print(f"Auth failure [{exc.code}] {exc.message} trace={exc.trace_id}")
        return

    session.token = token.access_token
    user = session.auth_client().me()
    print(f"Logged in as {user.username}")

    stock = session.stock_client()
    full_table = stock.get_stock(StockQuery(page=1, page_size=100))
    print(f"stock rows={len(full_table.rows)} totals={full_table.totals.model_dump(exclude_none=True)}")

    keys = stock.idempotency_keys()
    stock.import_sku(
        transaction_id=keys.transaction_id,
        idempotency_key=keys.idempotency_key,
        lines=[StockImportSkuLine(sku="SKU-1", qty=1, location_code="SELL-01", pool="ON_HAND")],
    )


if __name__ == "__main__":
    main()
