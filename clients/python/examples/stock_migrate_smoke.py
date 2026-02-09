from __future__ import annotations

import argparse
import json
import os

from aris3_client_sdk import ApiSession, ClientValidationError, load_config, new_idempotency_keys
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.stock_validation import ValidationIssue, validate_migration_line


def _load_payload(path: str | None) -> dict:
    if path:
        if os.path.splitext(path)[1].lower() != ".json":
            raise ValueError("Migration expects a JSON file.")
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        data = {
            "epc": "B" * 24,
            "data": {
                "sku": "SKU-1",
                "description": "Blue Jacket",
                "var1_value": "Blue",
                "var2_value": "L",
                "epc": None,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "PENDING",
                "location_is_vendible": True,
                "image_asset_id": None,
                "image_url": None,
                "image_thumb_url": None,
                "image_source": None,
                "image_updated_at": None,
            },
        }
    if isinstance(data, dict) and "lines" in data:
        data = data["lines"]
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError("Migration requires exactly one payload.")
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError("Input must be a migration payload object.")
    return data


def _format_issues(issues: list[ValidationIssue]) -> str:
    return "; ".join(
        f"row {issue.row_index} {issue.field}: {issue.reason}" if issue.row_index is not None else f"{issue.field}: {issue.reason}"
        for issue in issues
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS3 stock migrate-sku-to-epc smoke CLI")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--input", help="Path to JSON file")
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = StockClient(http=session._http(), access_token=session.token)

    try:
        payload = _load_payload(args.input)
        normalized = validate_migration_line(payload, row_index=0).model_dump(mode="json", exclude_none=True)
        keys = new_idempotency_keys()
        response = client.migrate_sku_to_epc([normalized], transaction_id=keys.transaction_id, idempotency_key=keys.idempotency_key)
        print(json.dumps({"accepted": response.migrated, "rejected": 0, "trace_id": response.trace_id}, indent=2))
    except ClientValidationError as exc:
        print(json.dumps({"accepted": 0, "rejected": len(exc.issues), "errors": _format_issues(exc.issues)}, indent=2))
        raise SystemExit(1) from exc
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
