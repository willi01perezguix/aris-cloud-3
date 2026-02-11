from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    status: str
    details: str


@dataclass
class CheckContext:
    strict: bool


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_file(path: Path) -> ast.AST:
    return ast.parse(_load_text(path), filename=str(path))


def _extract_model_fields(tree: ast.AST, class_name: str) -> set[str]:
    fields: set[str] = set()
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for inner in node.body:
                if isinstance(inner, ast.AnnAssign) and isinstance(inner.target, ast.Name):
                    fields.add(inner.target.id)
    return fields


def check_stock_full_table_contract() -> CheckResult:
    schema_path = ROOT / "app/aris3/schemas/stock.py"
    router_path = ROOT / "app/aris3/routers/stock.py"

    missing_files = [str(p.relative_to(ROOT)) for p in (schema_path, router_path) if not p.exists()]
    if missing_files:
        return CheckResult(
            name="stock full-table contract presence",
            status="FAIL",
            details=f"required files missing: {', '.join(missing_files)}",
        )

    schema_tree = _parse_file(schema_path)
    response_fields = _extract_model_fields(schema_tree, "StockQueryResponse")
    totals_fields = _extract_model_fields(schema_tree, "StockQueryTotals")

    required_response = {"meta", "rows", "totals"}
    required_totals = {"total_rows", "total_rfid", "total_pending", "total_units"}

    router_text = _load_text(router_path)
    has_stock_route = '@router.get("/aris3/stock"' in router_text
    has_response_model = "response_model=StockQueryResponse" in router_text

    missing_response = sorted(required_response - response_fields)
    missing_totals = sorted(required_totals - totals_fields)

    if missing_response or missing_totals or not has_stock_route or not has_response_model:
        return CheckResult(
            name="stock full-table contract presence",
            status="FAIL",
            details=(
                f"missing_response_keys={missing_response}, missing_totals_keys={missing_totals}, "
                f"stock_route_present={has_stock_route}, response_model_bound={has_response_model}"
            ),
        )

    return CheckResult(
        name="stock full-table contract presence",
        status="PASS",
        details="StockQueryResponse has meta/rows/totals and GET /aris3/stock route binds response model",
    )


def check_forbidden_state_transition_paths() -> CheckResult:
    routers_dir = ROOT / "app/aris3/routers"
    if not routers_dir.exists():
        return CheckResult(
            name="forbidden state-transition paths",
            status="FAIL",
            details="router directory not found: app/aris3/routers",
        )

    suspicious_tokens = ("status", "state", "transition", "activate", "deactivate", "close", "dispatch", "receive")
    decorator_pattern = re.compile(r"@router\.(post|patch|put|delete)\(\s*\"([^\"]+)\"")

    suspicious: list[str] = []
    for file in sorted(routers_dir.glob("*.py")):
        text = _load_text(file)
        for method, path in decorator_pattern.findall(text):
            path_lower = path.lower()
            if "/actions" in path_lower:
                continue
            if any(token in path_lower for token in suspicious_tokens):
                suspicious.append(f"{file.relative_to(ROOT)}:{method.upper()} {path}")

    # NOTE: This is heuristic static scanning; dynamic policy checks can be added later.
    if suspicious:
        return CheckResult(
            name="forbidden state-transition paths",
            status="WARN",
            details=f"suspicious non-/actions mutation routes detected ({len(suspicious)}): {suspicious[:5]}",
        )

    return CheckResult(
        name="forbidden state-transition paths",
        status="PASS",
        details="No suspicious transition-like mutation routes found outside /actions (heuristic scan)",
    )


def check_total_invariant_hooks() -> CheckResult:
    repo_path = ROOT / "app/aris3/repos/stock.py"
    if not repo_path.exists():
        return CheckResult(
            name="TOTAL invariant hooks",
            status="FAIL",
            details="stock repository not found: app/aris3/repos/stock.py",
        )

    text = _load_text(repo_path)
    has_total_units_expr = "total_units" in text and "total_rfid + total_pending" in text
    has_sellable_filters = "location_is_vendible" in text and 'status == "RFID"' in text and 'status == "PENDING"' in text

    # TODO: Add runtime DB-level invariant assertions once deterministic fixture harness is standardized for Sprint 7.
    if not has_total_units_expr or not has_sellable_filters:
        return CheckResult(
            name="TOTAL invariant hooks",
            status="FAIL",
            details=(
                f"has_total_units_expr={has_total_units_expr}, has_sellable_filters={has_sellable_filters}; "
                "operator: run stock smoke tests to validate TOTAL=RFID+PENDING behavior"
            ),
        )

    return CheckResult(
        name="TOTAL invariant hooks",
        status="PASS",
        details="Static invariant hooks detected in stock repository (TOTAL derived from RFID + PENDING in sellable scope)",
    )


def check_critical_route_map_sanity() -> CheckResult:
    expected_routes: dict[Path, list[str]] = {
        ROOT / "app/aris3/routers/stock.py": [
            "@router.get(\"/aris3/stock\"",
            "@router.post(\"/aris3/stock/import-epc\"",
            "@router.post(\"/aris3/stock/import-sku\"",
            "@router.post(\"/aris3/stock/migrate-sku-to-epc\"",
            "@router.post(\"/aris3/stock/actions\"",
        ],
        ROOT / "app/aris3/routers/transfers.py": ["@router.post(\"/aris3/transfers/{transfer_id}/actions\""],
        ROOT / "app/aris3/routers/pos_sales.py": ["@router.post(\"/aris3/pos/sales/{sale_id}/actions\""],
        ROOT / "app/aris3/routers/pos_cash.py": [
            "@router.post(\"/aris3/pos/cash/session/actions\"",
            "@router.post(\"/aris3/pos/cash/day-close/actions\"",
        ],
    }

    missing: list[str] = []
    for file, markers in expected_routes.items():
        if not file.exists():
            missing.append(f"{file.relative_to(ROOT)} (file missing)")
            continue
        text = _load_text(file)
        for marker in markers:
            if marker not in text:
                missing.append(f"{file.relative_to(ROOT)} missing marker: {marker}")

    if missing:
        return CheckResult(
            name="critical route map sanity",
            status="FAIL",
            details=f"missing critical route markers ({len(missing)}): {missing[:8]}",
        )

    return CheckResult(
        name="critical route map sanity",
        status="PASS",
        details="Critical stock/transfer/POS route markers present",
    )


def run_checks(ctx: CheckContext) -> list[CheckResult]:
    return [
        check_stock_full_table_contract(),
        check_forbidden_state_transition_paths(),
        check_total_invariant_hooks(),
        check_critical_route_map_sanity(),
    ]


def _render_table(results: list[CheckResult]) -> str:
    lines = [
        "Contract Safety Check Summary",
        "=" * 112,
        f"{'CHECK':40} {'STATUS':8} DETAILS",
        "-" * 112,
    ]
    for result in results:
        lines.append(f"{result.name:40} {result.status:8} {result.details}")
    lines.append("=" * 112)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 7 contract safety checks (non-destructive static guardrails)")
    parser.add_argument("--strict", action="store_true", help="treat WARN checks as failures")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    results = run_checks(CheckContext(strict=args.strict))
    failing = {"FAIL"}
    if args.strict:
        failing.add("WARN")
    has_failure = any(item.status in failing for item in results)

    payload = {
        "strict": args.strict,
        "results": [asdict(item) for item in results],
        "operator_instructions": [
            "Run with --strict in CI and block merge on failures.",
            "If WARN appears in non-strict mode, investigate and convert to explicit allowlist or fix route design.",
            "TODO: augment with runtime fixture checks for invariant validation once Sprint 7 fixtures are finalized.",
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_render_table(results))
        print(
            "\nOperator commands:\n"
            "  python scripts/contract_safety_check.py --strict\n"
            "  python scripts/contract_safety_check.py --strict --json > artifacts/contract_safety_report.json"
        )

    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
