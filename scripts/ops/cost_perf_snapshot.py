from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for file in sorted(path.rglob("*")):
        if file.is_file():
            total += int(file.stat().st_size)
    return total


def _status(value: float, warn: float, fail: float) -> str:
    if value >= fail:
        return "fail"
    if value >= warn:
        return "warn"
    return "pass"


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-GA Day4 cost/performance snapshot analyzer")
    parser.add_argument("--artifact-dir", default="artifacts/post-ga/day4")
    parser.add_argument("--baseline", default="docs/ops/COST_PERF_BASELINE_DAY4.json")
    parser.add_argument("--strict-gate", action="store_true", default=False)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / args.artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline = _read_json(repo_root / args.baseline) or {}
    day2_results = _read_json(repo_root / "artifacts/post-ga/day2/results.json")
    day3_summary = _read_json(repo_root / "artifacts/post-ga/day3/summary.json")

    missing_input: list[str] = []
    if day2_results is None:
        missing_input.append("artifacts/post-ga/day2/results.json")
    if day3_summary is None:
        missing_input.append("artifacts/post-ga/day3/summary.json")

    day2_total_runtime = 0.0
    if isinstance(day2_results, list):
        day2_total_runtime = round(sum(float(row.get("duration_seconds", 0.0)) for row in day2_results), 3)

    p95 = None
    error_rate = None
    if isinstance(day3_summary, dict):
        p95 = day3_summary.get("latency_ms", {}).get("p95")
        error_rate = day3_summary.get("totals", {}).get("error_rate")

    artifact_sizes = {
        "day2": _dir_size_bytes(repo_root / "artifacts/post-ga/day2"),
        "day3": _dir_size_bytes(repo_root / "artifacts/post-ga/day3"),
        "day4": _dir_size_bytes(repo_root / "artifacts/post-ga/day4"),
    }
    artifact_total_mb = round(sum(artifact_sizes.values()) / (1024 * 1024), 3)

    budgets = baseline.get("budgets", {})
    runtime_budget_warn = float(budgets.get("ci_runtime_total_seconds_warn", 900.0))
    runtime_budget_fail = float(budgets.get("ci_runtime_total_seconds_fail", 1200.0))
    artifact_budget_warn = float(budgets.get("artifact_footprint_mb_warn", 250.0))
    artifact_budget_fail = float(budgets.get("artifact_footprint_mb_fail", 500.0))
    p95_warn = float(budgets.get("day3_p95_ms_warn", 1200.0))
    p95_fail = float(budgets.get("day3_p95_ms_fail", 1500.0))

    compliance = {
        "ci_runtime_total_seconds": {
            "value": day2_total_runtime,
            "status": _status(day2_total_runtime, runtime_budget_warn, runtime_budget_fail),
        },
        "artifact_footprint_mb": {
            "value": artifact_total_mb,
            "status": _status(artifact_total_mb, artifact_budget_warn, artifact_budget_fail),
        },
        "day3_p95_ms": {
            "value": p95,
            "status": "warn" if p95 is None else _status(float(p95), p95_warn, p95_fail),
        },
    }

    overall = "pass"
    statuses = [metric["status"] for metric in compliance.values()]
    if "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"

    trend = {
        "runtime_vs_baseline_seconds": None,
        "artifact_vs_baseline_mb": None,
    }
    prior = baseline.get("prior_baseline", {})
    if "ci_runtime_total_seconds" in prior:
        trend["runtime_vs_baseline_seconds"] = round(day2_total_runtime - float(prior["ci_runtime_total_seconds"]), 3)
    if "artifact_footprint_mb" in prior:
        trend["artifact_vs_baseline_mb"] = round(artifact_total_mb - float(prior["artifact_footprint_mb"]), 3)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "missing_input": missing_input,
        "runtime_envelope": {
            "day2_total_runtime_seconds": day2_total_runtime,
        },
        "artifact_footprint": {
            "bytes_by_scope": artifact_sizes,
            "total_mb": artifact_total_mb,
        },
        "trend": trend,
        "budget_compliance": compliance,
        "budget_status": overall,
        "go_no_go": "NO-GO" if (args.strict_gate and overall == "fail") else "GO",
    }

    _write_json(out_dir / "cost_perf_summary.json", summary)

    with (out_dir / "cost_perf_table.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value", "status"])
        writer.writeheader()
        for key in sorted(compliance):
            writer.writerow({"metric": key, "value": compliance[key]["value"], "status": compliance[key]["status"]})

    print(f"cost/perf snapshot complete: budget_status={overall} go_no_go={summary['go_no_go']}")
    return 1 if (args.strict_gate and overall == "fail") else 0


if __name__ == "__main__":
    raise SystemExit(main())
