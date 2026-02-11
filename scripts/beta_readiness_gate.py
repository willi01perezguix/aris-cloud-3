from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass
class GateResult:
    name: str
    status: str
    detail: str
    elapsed_sec: float


def run_command(name: str, command: list[str], *, cwd: Path | None = None) -> GateResult:
    start = time.perf_counter()
    proc = subprocess.run(command, cwd=cwd or ROOT_DIR, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    out_lines = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = out_lines[-1] if out_lines else "ok"
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return GateResult(name=name, status=status, detail=detail[:180], elapsed_sec=elapsed)


def collect_results() -> list[GateResult]:
    return [
        run_command(
            "smoke:deterministic",
            [
                "pytest",
                "-q",
                "clients/python/tests/test_module_imports_day4.py",
                "clients/python/tests/test_clients.py",
            ],
        ),
        run_command("contract:safety", [sys.executable, "scripts/contract_safety_check.py", "--strict"]),
        run_command("packaging:scaffold", ["pytest", "-q", "clients/python/tests/test_packaging_scaffold.py"]),
        run_command(
            "shared:telemetry-flags-tests",
            [
                "pytest",
                "-q",
                "clients/python/tests/shared/test_telemetry.py",
                "clients/python/tests/shared/test_feature_flags.py",
                "clients/python/tests/planning_or_ops/test_beta_gate.py",
            ],
        ),
    ]


def summarize(results: list[GateResult]) -> str:
    lines = [
        "Sprint 8 Day 1 Beta Readiness Gate",
        "=" * 100,
        f"{'CHECK':34} {'STATUS':8} {'ELAPSED(s)':10} DETAIL",
        "-" * 100,
    ]
    for result in results:
        lines.append(f"{result.name:34} {result.status:8} {result.elapsed_sec:10.2f} {result.detail}")
    lines.append("=" * 100)
    return "\n".join(lines)


def gate_exit_code(results: list[GateResult]) -> int:
    return 1 if any(item.status == "FAIL" for item in results) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 8 Day 1 beta-readiness baseline gate")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first blocker")
    args = parser.parse_args()

    if args.fail_fast:
        results: list[GateResult] = []
        for check in collect_results():
            results.append(check)
            if check.status == "FAIL":
                break
    else:
        results = collect_results()

    print(summarize(results))
    code = gate_exit_code(results)
    print("Gate result: PASS" if code == 0 else "Gate result: FAIL")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
