from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    elapsed_sec: float


def _run_command(name: str, command: list[str], *, env: dict | None = None) -> CheckResult:
    start = time.perf_counter()
    proc = subprocess.run(command, capture_output=True, text=True, env=env)
    elapsed = time.perf_counter() - start
    output = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = output[-1] if output else "ok"
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return CheckResult(name=name, status=status, detail=detail[:180], elapsed_sec=elapsed)


def _check_test_matrix(pytest_target: str, postgres_url: str | None) -> list[CheckResult]:
    results: list[CheckResult] = []

    sqlite_env = os.environ.copy()
    sqlite_env["DATABASE_URL"] = sqlite_env.get("DATABASE_URL", "sqlite+pysqlite:///./release-gate-sqlite.db")
    results.append(
        _run_command(
            "tests:sqlite",
            ["pytest", "-q", pytest_target],
            env=sqlite_env,
        )
    )

    if postgres_url:
        pg_env = os.environ.copy()
        pg_env["DATABASE_URL"] = postgres_url
        results.append(_run_command("tests:postgres", ["pytest", "-q", pytest_target], env=pg_env))
    else:
        results.append(
            CheckResult(
                name="tests:postgres",
                status="WARN",
                detail="skipped (POSTGRES_GATE_URL not provided)",
                elapsed_sec=0.0,
            )
        )

    return results


def _migration_safety_check() -> CheckResult:
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_url = f"sqlite+pysqlite:///{Path(tmp) / 'migration_gate.db'}"
        env = os.environ.copy()
        env["DATABASE_URL"] = sqlite_url
        commands = [
            ["alembic", "upgrade", "head"],
            ["alembic", "downgrade", "base"],
            ["alembic", "upgrade", "head"],
        ]
        for command in commands:
            proc = subprocess.run(command, capture_output=True, text=True, env=env)
            if proc.returncode != 0:
                elapsed = time.perf_counter() - start
                detail = (proc.stderr or proc.stdout or "migration command failed").strip().splitlines()[-1]
                return CheckResult("migration:safety", "FAIL", detail[:180], elapsed)
    elapsed = time.perf_counter() - start
    return CheckResult("migration:safety", "PASS", "upgrade/downgrade/upgrade succeeded", elapsed)


def _security_sanity_check() -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.append(
        _run_command(
            "security:admin-boundary",
            ["pytest", "-q", "tests/test_admin_core.py::test_admin_user_cross_tenant_denied"],
        )
    )

    debug_enabled = os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}
    status = "FAIL" if debug_enabled else "PASS"
    checks.append(
        CheckResult(
            name="security:debug-config",
            status=status,
            detail="DEBUG env must not be enabled in release path",
            elapsed_sec=0.0,
        )
    )
    return checks


def _performance_sanity_check(budget_ms: float) -> CheckResult:
    start = time.perf_counter()
    os.environ.setdefault("SECRET_KEY", "release-gate-secret")
    from app.main import create_app

    app = create_app()
    sample_latencies = []
    with TestClient(app) as client:
        for _ in range(20):
            tick = time.perf_counter()
            response = client.get("/health")
            sample_latencies.append((time.perf_counter() - tick) * 1000)
            if response.status_code != 200:
                elapsed = time.perf_counter() - start
                return CheckResult("performance:p95-health", "FAIL", "health endpoint failed", elapsed)

    sample_latencies.sort()
    p95 = sample_latencies[max(0, int(len(sample_latencies) * 0.95) - 1)]
    status = "PASS" if p95 <= budget_ms else "FAIL"
    elapsed = time.perf_counter() - start
    return CheckResult(
        "performance:p95-health",
        status,
        f"p95={p95:.2f}ms (budget={budget_ms:.2f}ms)",
        elapsed,
    )


def _readiness_diagnostics_check() -> CheckResult:
    start = time.perf_counter()
    os.environ.setdefault("SECRET_KEY", "release-gate-secret")
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")

    ok = health.status_code == 200 and ready.status_code == 200
    status = "PASS" if ok else "FAIL"
    detail = f"health={health.status_code}, ready={ready.status_code}"
    return CheckResult("ops:health-readiness", status, detail, time.perf_counter() - start)


def _print_summary(results: list[CheckResult]) -> None:
    print("\nRelease Readiness Gate Summary")
    print("=" * 96)
    print(f"{'CHECK':40} {'STATUS':8} {'ELAPSED(s)':10} DETAIL")
    print("-" * 96)
    for item in results:
        print(f"{item.name:40} {item.status:8} {item.elapsed_sec:10.2f} {item.detail}")
    print("=" * 96)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 6 Day 6 release readiness gate")
    parser.add_argument("--pytest-target", default="tests", help="pytest target for matrix checks")
    parser.add_argument("--postgres-url", default=os.getenv("POSTGRES_GATE_URL"), help="Postgres URL for gate matrix")
    parser.add_argument("--perf-p95-budget-ms", type=float, default=120.0, help="Local p95 budget for /health")
    args = parser.parse_args()

    all_results: list[CheckResult] = []
    all_results.extend(_check_test_matrix(args.pytest_target, args.postgres_url))
    all_results.append(_migration_safety_check())
    all_results.append(_run_command("smoke:critical", ["pytest", "-q", "tests/smoke/test_post_merge_readiness.py"]))
    all_results.extend(_security_sanity_check())
    all_results.append(_readiness_diagnostics_check())
    all_results.append(_performance_sanity_check(args.perf_p95_budget_ms))

    _print_summary(all_results)

    blockers = [item for item in all_results if item.status == "FAIL"]
    if blockers:
        print(f"Gate result: FAIL ({len(blockers)} blocker(s))")
        return 1

    warns = [item for item in all_results if item.status == "WARN"]
    if warns:
        print(f"Gate result: PASS_WITH_WARNINGS ({len(warns)} warning(s))")
    else:
        print("Gate result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
