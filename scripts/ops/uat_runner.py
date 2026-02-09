from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("artifacts/release_candidate")


UAT_CASES = [
    {
        "module": "Auth/Me",
        "cases": [
            "login / change-password / me",
            "must_change_password",
            "scope tenant correcto",
        ],
    },
    {
        "module": "Stock",
        "cases": [
            "import-epc (qty=1, EPC 24 HEX único)",
            "import-sku (suma PENDING)",
            "migrate-sku-to-epc (PENDING-1, RFID+1, total constante)",
            "GET /stock full-table con filtros + invariantes de totales",
        ],
    },
    {
        "module": "Transfers",
        "cases": [
            "draft -> dispatch -> receive total/parcial",
            "report_shortages y resolve_shortages (FOUND_AND_RESEND / LOST_IN_ROUTE MANAGER-only)",
            "validaciones: mismo tenant, no auto-traslado, recepción solo destino",
        ],
    },
    {
        "module": "POS Sales + Cash",
        "cases": [
            "checkout con CASH/CARD/TRANSFER/mixed",
            "reglas de cambio (solo CASH)",
            "sesión OPEN obligatoria para CASH",
            "cancel / validaciones de estado",
        ],
    },
    {
        "module": "Refund/Exchange",
        "cases": [
            "REFUND_ITEMS y EXCHANGE_ITEMS atómicos",
            "aplicación de return-policy",
            "cash refund => CASH_OUT_REFUND",
        ],
    },
    {
        "module": "Inventory Counts",
        "cases": [
            "START/PAUSE/RESUME/CLOSE/CANCEL/RECONCILE",
            "bloqueo duro por tienda durante conteo",
            "snapshot + diferencias",
        ],
    },
    {
        "module": "Media",
        "cases": [
            "resolución VARIANT->SKU->PLACEHOLDER",
            "stock devuelve image_* correctamente",
        ],
    },
    {
        "module": "Admin + RBAC",
        "cases": [
            "ADMIN ceiling tenant",
            "effective-permissions coherente",
            "denegaciones auditables",
        ],
    },
]


def _build_cases(status: str, note: str) -> list[dict]:
    rows: list[dict] = []
    for module in UAT_CASES:
        for description in module["cases"]:
            rows.append(
                {
                    "module": module["module"],
                    "description": description,
                    "status": status,
                    "notes": note,
                }
            )
    return rows


def _summarize(cases: list[dict]) -> dict:
    summary = {"PASS": 0, "FAIL": 0, "NOT_EXECUTED": 0}
    for case in cases:
        summary[case["status"]] = summary.get(case["status"], 0) + 1
    summary["total"] = len(cases)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate UAT report scaffold for ARIS3")
    parser.add_argument("--status", default="NOT_EXECUTED", choices=["PASS", "FAIL", "NOT_EXECUTED"])
    parser.add_argument("--note", default="UAT automation not executed in this environment.")
    parser.add_argument("--output-json", help="Output JSON path")
    parser.add_argument("--output-md", help="Output Markdown path")
    args = parser.parse_args()

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_json = Path(args.output_json) if args.output_json else DEFAULT_OUTPUT_DIR / "uat_report.json"
    output_md = Path(args.output_md) if args.output_md else DEFAULT_OUTPUT_DIR / "uat_report.md"

    cases = _build_cases(args.status, args.note)
    payload = {
        "run_id": time.strftime("%Y%m%d-%H%M%S"),
        "status": args.status,
        "note": args.note,
        "summary": _summarize(cases),
        "cases": cases,
    }

    output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    lines = [
        "# UAT Report — Sprint 4 Día 7",
        "",
        f"Estado general: **{args.status}**",
        "",
        f"Nota: {args.note}",
        "",
        "## Resumen",
        f"- Total casos: {payload['summary']['total']}",
        f"- PASS: {payload['summary']['PASS']}",
        f"- FAIL: {payload['summary']['FAIL']}",
        f"- NOT_EXECUTED: {payload['summary']['NOT_EXECUTED']}",
        "",
        "## Matriz",
    ]
    for case in cases:
        lines.append(f"- [{case['status']}] {case['module']} — {case['description']} (nota: {case['notes']})")
    output_md.write_text("\n".join(lines))

    print(output_json)
    print(output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
