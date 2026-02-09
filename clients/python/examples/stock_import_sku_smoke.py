from __future__ import annotations

import argparse
import csv
import json
import os

from aris3_client_sdk import ApiSession, ClientValidationError, load_config, new_idempotency_keys
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.stock_validation import ValidationIssue, validate_import_sku_line


def _load_payload(path: str | None) -> list[dict]:
    if path:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return _normalize_payload(data)
        if ext == ".csv":
            with open(path, "r", encoding="utf-8", newline="") as handle:
                return [row for row in csv.DictReader(handle)]
        raise ValueError("Unsupported file type; use .json or .csv")
    return [
        {
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
            "qty": 2,
        }
    ]


def _normalize_payload(data: object) -> list[dict]:
    if isinstance(data, dict) and "lines" in data:
        data = data["lines"]
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("Input must be a list of line objects.")


def _validate_lines(lines: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    issues: list[ValidationIssue] = []
    for idx, line in enumerate(lines):
        try:
            normalized.append(validate_import_sku_line(line, idx).model_dump(mode="json", exclude_none=True))
        except ClientValidationError as exc:
            issues.extend(exc.issues)
    if issues:
        raise ClientValidationError(issues)
    return normalized


def _format_issues(issues: list[ValidationIssue]) -> str:
    return "; ".join(
        f"row {issue.row_index} {issue.field}: {issue.reason}" if issue.row_index is not None else f"{issue.field}: {issue.reason}"
        for issue in issues
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS3 stock import-sku smoke CLI")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--input", help="Path to JSON or CSV file")
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = StockClient(http=session._http(), access_token=session.token)

    try:
        lines = _load_payload(args.input)
        normalized = _validate_lines(lines)
        keys = new_idempotency_keys()
        response = client.import_sku(normalized, transaction_id=keys.transaction_id, idempotency_key=keys.idempotency_key)
        print(json.dumps({"accepted": response.processed, "rejected": 0, "trace_id": response.trace_id}, indent=2))
    except ClientValidationError as exc:
        print(json.dumps({"accepted": 0, "rejected": len(exc.issues), "errors": _format_issues(exc.issues)}, indent=2))
        raise SystemExit(1) from exc
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
