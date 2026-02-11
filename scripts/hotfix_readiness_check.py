from __future__ import annotations

from pathlib import Path
import subprocess
from dataclasses import dataclass

REQUIRED_FILES = [
    "runbooks/13_HOTFIX_PROTOCOL_ARIS3_v1.md",
    "tests/smoke/test_post_go_live_stability.py",
    "scripts/post_go_live_integrity_check.py",
]


@dataclass
class Check:
    name: str
    ok: bool
    details: str


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> int:
    checks: list[Check] = []

    branch = _git("branch", "--show-current")
    checks.append(Check("branch naming", branch.startswith("hotfix/") or branch.startswith("sprint6-day8"), f"branch={branch}"))

    status = _git("status", "--porcelain")
    checks.append(Check("working tree review", True, "dirty tree allowed; ensure intentional files only" if status else "clean"))

    for path in REQUIRED_FILES:
        exists = Path(path).exists()
        checks.append(Check(f"required file: {path}", exists, "present" if exists else "missing"))

    print("Hotfix Readiness Summary")
    print("=" * 88)
    for check in checks:
        label = "PASS" if check.ok else "FAIL"
        print(f"{check.name:52} {label:6} {check.details}")

    failures = [c for c in checks if not c.ok]
    if failures:
        print(f"Result: FAIL ({len(failures)} blocker checks)")
        return 1
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
