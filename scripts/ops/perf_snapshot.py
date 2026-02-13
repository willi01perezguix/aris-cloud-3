from __future__ import annotations

import argparse
import json
import platform
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SLOWEST_RE = re.compile(r"^\s*(?P<seconds>\d+\.\d+)s\s+(?P<kind>\w+)\s+(?P<nodeid>.+)$")


@dataclass(frozen=True)
class Check:
    name: str
    command: str
    required: bool = True


def _command_matrix(run_full_suite: bool) -> list[Check]:
    checks = [
        Check("Packaging scaffold (repo path)", "python -m pytest clients/python/tests/test_packaging_scaffold.py -q"),
        Check(
            "Packaging scaffold (clients/python cwd)",
            "python -m pytest tests/test_packaging_scaffold.py -q",
        ),
        Check(
            "Timezone boundary report",
            "python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv",
        ),
        Check(
            "Go-live smoke POS checkout and reports",
            "python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv",
        ),
        Check("Packaging scripts contract", "python -m pytest tests/packaging/test_packaging_scripts_contract.py -q"),
    ]
    if run_full_suite:
        checks.append(Check("Full suite gate", "python -m pytest tests -q -x --maxfail=1", required=False))
    return checks


def _run_command(command: str, cwd: Path) -> tuple[int, str, float]:
    parts = shlex.split(command)
    if len(parts) >= 3 and parts[0] == "python" and parts[1] == "-m" and parts[2] == "pytest":
        parts.extend(["--durations=10", "--durations-min=0"])
    started = datetime.now(timezone.utc)
    completed = subprocess.run(parts, cwd=str(cwd), capture_output=True, text=True)
    ended = datetime.now(timezone.utc)
    elapsed = (ended - started).total_seconds()
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output, elapsed


def _extract_slowest(output: str, check_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        match = SLOWEST_RE.match(line)
        if not match:
            continue
        rows.append(
            {
                "check": check_name,
                "seconds": float(match.group("seconds")),
                "kind": match.group("kind"),
                "nodeid": match.group("nodeid"),
            }
        )
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-GA Day2 performance baseline snapshot")
    parser.add_argument("--artifact-dir", default="artifacts/post-ga/day2")
    parser.add_argument("--full-suite", action="store_true")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=repo_root).strip()
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    python_version = sys.version.replace("\n", " ").strip()
    platform_text = platform.platform()

    checks = _command_matrix(run_full_suite=args.full_suite)
    matrix_payload = [
        {"index": i + 1, "name": check.name, "command": check.command, "required": check.required}
        for i, check in enumerate(checks)
    ]

    results: list[dict[str, Any]] = []
    slowest: list[dict[str, Any]] = []

    for check in checks:
        cwd = repo_root
        if check.name == "Packaging scaffold (clients/python cwd)":
            cwd = repo_root / "clients/python"
        code, output, elapsed = _run_command(check.command, cwd)
        passed = code == 0
        results.append(
            {
                "name": check.name,
                "required": check.required,
                "command": check.command,
                "cwd": str(cwd.relative_to(repo_root)) if cwd != repo_root else ".",
                "exit_code": code,
                "status": "PASS" if passed else "FAIL",
                "duration_seconds": round(elapsed, 3),
            }
        )
        (artifact_dir / f"{re.sub(r'[^a-z0-9]+', '_', check.name.lower()).strip('_')}.log").write_text(output, encoding="utf-8")
        slowest.extend(_extract_slowest(output, check.name))

    required_results = [r for r in results if r["required"]]
    pass_count = sum(1 for r in required_results if r["status"] == "PASS")
    fail_count = sum(1 for r in required_results if r["status"] == "FAIL")
    decision = "GO" if fail_count == 0 else "NO-GO"

    metadata = {
        "sha": sha,
        "timestamp_utc": timestamp_utc,
        "python_version": python_version,
        "platform": platform_text,
        "run_full_suite": bool(args.full_suite),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "result": decision,
    }

    _write_json(artifact_dir / "metadata.json", metadata)
    _write_json(artifact_dir / "command_matrix.json", matrix_payload)
    _write_json(artifact_dir / "results.json", results)
    _write_json(
        artifact_dir / "pytest_durations_summary.json",
        {
            "slowest_tests": sorted(slowest, key=lambda row: row["seconds"], reverse=True)[:20],
            "count": len(slowest),
        },
    )

    summary_lines = [
        f"POST-GA DAY2 RESULT: {decision}",
        f"Required checks: {len(required_results)}",
        f"Pass: {pass_count}",
        f"Fail: {fail_count}",
        f"Artifacts: {artifact_dir}",
    ]
    (artifact_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(" | ".join(summary_lines[:4]))

    return 0 if decision == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
