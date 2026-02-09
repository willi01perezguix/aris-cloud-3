from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("artifacts/release_candidate")


def _run_rg(pattern: str, *paths: str) -> dict:
    command = ["rg", "-n", pattern, *paths]
    proc = subprocess.run(command, capture_output=True, text=True)
    matches = proc.stdout.strip().splitlines() if proc.stdout.strip() else []
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "matches": matches,
    }


def _run_pip_audit() -> dict:
    command = ["python", "-m", "pip_audit", "-r", "requirements.txt"]
    proc = subprocess.run(command, capture_output=True, text=True)
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Security gate checks for ARIS3")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / "security_gate_summary.json"

    checks = []

    secrets_check = _run_rg(r"logger\.(info|warning|error|debug|exception).*?(password|secret|token)", "app")
    secrets_status = "PASS" if secrets_check["returncode"] == 1 else "FAIL"
    checks.append(
        {
            "id": "secrets_in_logs",
            "status": secrets_status,
            "details": secrets_check,
        }
    )

    rbac_check = _run_rg(r"require_permissions", "app/aris3/routers")
    rbac_status = "PASS" if rbac_check["returncode"] == 0 else "WARN"
    checks.append(
        {
            "id": "rbac_controls_present",
            "status": rbac_status,
            "details": rbac_check,
        }
    )

    pip_audit = _run_pip_audit()
    if pip_audit["returncode"] == 0:
        dep_status = "PASS"
    elif "No module named" in pip_audit["stderr"]:
        dep_status = "WARN"
    else:
        dep_status = "FAIL"
    checks.append(
        {
            "id": "dependency_audit",
            "status": dep_status,
            "details": pip_audit,
        }
    )

    overall = "PASS"
    for check in checks:
        if check["status"] == "FAIL":
            overall = "FAIL"
            break
        if check["status"] == "WARN":
            overall = "WARN"

    payload = {
        "status": overall,
        "checks": checks,
    }

    output_path.write_text(json.dumps(payload, indent=2))
    print(output_path)
    return 0 if overall == "PASS" else 1 if overall == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
