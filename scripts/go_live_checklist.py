from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    elapsed_sec: float


def _run_command(name: str, command: list[str], *, dry_run: bool, env: dict[str, str] | None = None) -> CheckResult:
    if dry_run:
        return CheckResult(name=name, status="DRY-RUN", detail=" ".join(command), elapsed_sec=0.0)

    start = time.perf_counter()
    proc = subprocess.run(command, capture_output=True, text=True, env=env)
    elapsed = time.perf_counter() - start
    output_lines = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = output_lines[-1] if output_lines else "ok"
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return CheckResult(name=name, status=status, detail=detail[:200], elapsed_sec=elapsed)


def _print_summary(results: list[CheckResult]) -> None:
    print("\nGo-Live Checklist Summary")
    print("=" * 108)
    print(f"{'CHECK':44} {'STATUS':10} {'ELAPSED(s)':10} DETAIL")
    print("-" * 108)
    for item in results:
        print(f"{item.name:44} {item.status:10} {item.elapsed_sec:10.2f} {item.detail}")
    print("=" * 108)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 6 Day 7 go-live preflight checklist")
    parser.add_argument("--dry-run", action="store_true", help="print commands without executing checks")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "sqlite+pysqlite:///./go-live-checklist.db"),
        help="database url used for smoke execution",
    )
    args = parser.parse_args()

    check_env = os.environ.copy()
    check_env["DATABASE_URL"] = args.database_url

    checks = [
        (
            "git:working-tree-clean",
            [
                "python",
                "-c",
                "import subprocess,sys; out=subprocess.check_output(['git','status','--porcelain'], text=True).strip(); "
                "sys.exit(1) if out else print('clean')",
            ],
        ),
        ("migrations:single-head", ["python", "-c", "import subprocess,sys; heads=[l for l in subprocess.check_output(['alembic','heads'], text=True).splitlines() if l.strip()]; sys.exit(1) if len(heads)!=1 else print(heads[0])"]),
        ("migrations:upgrade-head", ["alembic", "upgrade", "head"]),
        ("release-gate:day6", ["python", "scripts/release_readiness_gate.py", "--pytest-target", "tests/smoke/test_post_merge_readiness.py"]),
        ("smoke:go-live-day7", ["pytest", "-q", "tests/smoke/test_go_live_validation.py"]),
        ("health:ready-endpoints", ["python", "-c", "from fastapi.testclient import TestClient; from app.main import create_app; app=create_app(); c=TestClient(app); h=c.get('/health').status_code; r=c.get('/ready').status_code; print(f'health={h}, ready={r}'); raise SystemExit(0 if h==200 and r==200 else 1)"]),
    ]

    results: list[CheckResult] = []
    for name, command in checks:
        env = check_env if name in {"migrations:upgrade-head", "release-gate:day6", "smoke:go-live-day7"} else None
        result = _run_command(name, command, dry_run=args.dry_run, env=env)
        results.append(result)
        if result.status == "FAIL":
            break

    _print_summary(results)

    failures = [item for item in results if item.status == "FAIL"]
    if failures:
        print(f"Go-live checklist result: FAIL ({len(failures)} blocker(s))")
        return 1

    if args.dry_run:
        print("Go-live checklist result: DRY-RUN")
        return 0

    print("Go-live checklist result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
