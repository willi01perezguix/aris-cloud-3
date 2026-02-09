from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("artifacts/release_candidate")


def _run_pytest(database_url: str | None, extra_args: list[str]) -> dict:
    env = os.environ.copy()
    if database_url:
        env["DATABASE_URL"] = database_url
    command = ["pytest", "-q", *extra_args]
    started_at = time.time()
    proc = subprocess.run(command, capture_output=True, text=True, env=env)
    finished_at = time.time()
    return {
        "command": " ".join(command),
        "database_url": database_url,
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_sec": round(finished_at - started_at, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ARIS3 test matrix for a target database")
    parser.add_argument("--label", required=True, help="Label for this run (e.g., sqlite, postgres)")
    parser.add_argument("--database-url", help="Override DATABASE_URL for this run")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument("--pytest-arg", action="append", default=[], help="Extra pytest args")
    args = parser.parse_args()

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"test_matrix_{args.label}.json"

    result = _run_pytest(args.database_url, args.pytest_arg)
    payload = {
        "label": args.label,
        "result": result,
    }
    output_path.write_text(json.dumps(payload, indent=2))
    print(output_path)
    return 0 if result["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
