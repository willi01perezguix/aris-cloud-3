from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.pos_sales_client import PosSalesClient
from aris3_client_sdk.exceptions import ApiError


def _build_line(args: argparse.Namespace) -> dict:
    line_type = args.line_type.upper()
    if line_type not in {"SKU", "EPC"}:
        raise ValueError("line_type must be SKU or EPC")
    if line_type == "EPC" and not args.epc:
        raise ValueError("EPC line requires --epc")
    if line_type == "SKU" and not args.sku:
        raise ValueError("SKU line requires --sku")
    qty = 1 if line_type == "EPC" else args.qty
    status = "RFID" if line_type == "EPC" else "PENDING"
    return {
        "line_type": line_type,
        "qty": qty,
        "unit_price": args.unit_price,
        "snapshot": {
            "sku": args.sku,
            "description": args.description,
            "var1_value": args.var1,
            "var2_value": args.var2,
            "epc": args.epc if line_type == "EPC" else None,
            "location_code": args.location_code,
            "pool": args.pool,
            "status": status,
            "location_is_vendible": True,
        },
    }


def _line_from_response(line) -> dict:
    snapshot = line.snapshot.model_dump(mode="json", exclude_none=True) if line.snapshot else {}
    return {
        "line_type": line.line_type,
        "qty": line.qty,
        "unit_price": float(line.unit_price) if line.unit_price is not None else 0.0,
        "snapshot": snapshot,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Add items to a POS sale (smoke)")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--sale-id", required=True)
    parser.add_argument("--line-type", default="SKU")
    parser.add_argument("--sku")
    parser.add_argument("--epc")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--unit-price", type=float, default=0.0)
    parser.add_argument("--location-code", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--description")
    parser.add_argument("--var1")
    parser.add_argument("--var2")
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = PosSalesClient(http=session._http(), access_token=session.token)

    try:
        sale = client.get_sale(args.sale_id)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc

    existing_lines = [_line_from_response(line) for line in sale.lines]
    existing_lines.append(_build_line(args))
    keys = new_idempotency_keys()
    payload = {
        "transaction_id": keys.transaction_id,
        "lines": existing_lines,
    }

    try:
        response = client.update_sale(args.sale_id, payload, idempotency_key=keys.idempotency_key)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc

    print(f"Sale updated: {response.header.id} lines={len(response.lines)} status={response.header.status}")


if __name__ == "__main__":
    main()
