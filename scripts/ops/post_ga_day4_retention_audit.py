from __future__ import annotations

import argparse
import csv
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScopeRule:
    root: Path
    retention_days: int
    label: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except Exception:
        return "unknown"


def _is_tracked(repo_root: Path, candidate: Path) -> bool:
    rel = candidate.relative_to(repo_root)
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(rel)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _collect_candidates(repo_root: Path, rules: list[ScopeRule], now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rule in rules:
        root = rule.root
        if not root.exists():
            continue
        cutoff = now - timedelta(days=rule.retention_days)
        for path in sorted(root.rglob("*")):
            if not path.exists() or path.is_dir():
                continue
            if path.name in {
                "retention_audit_summary.json",
                "retention_candidates.csv",
                "retention_actions.log",
                "env_snapshot.json",
                "gate_result.txt",
            }:
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime > cutoff:
                continue
            size_bytes = int(path.stat().st_size)
            rows.append(
                {
                    "path": str(path.relative_to(repo_root)).replace("\\", "/"),
                    "size_bytes": size_bytes,
                    "mtime_utc": mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "retention_days": rule.retention_days,
                    "scope": rule.label,
                }
            )
    return rows


def _delete_path(path: Path) -> str:
    if path.is_dir():
        shutil.rmtree(path)
        return "deleted_dir"
    path.unlink(missing_ok=True)
    return "deleted_file"


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-GA Day4 retention audit (safe by default)")
    parser.add_argument("--artifact-dir", default="artifacts/post-ga/day4")
    parser.add_argument("--apply", action="store_true", default=False, help="Apply cleanup actions (default is dry-run)")
    parser.add_argument("--strict-gate", action="store_true", default=False)
    parser.add_argument("--post-ga-days", type=int, default=30)
    parser.add_argument("--diag-days", type=int, default=14)
    parser.add_argument("--temp-days", type=int, default=7)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    artifact_dir = repo_root / args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    now = _utc_now()

    rules = [
        ScopeRule(repo_root / "artifacts/post-ga", args.post_ga_days, "artifacts/post-ga"),
        ScopeRule(repo_root / "artifacts/diagnostics", args.diag_days, "artifacts/diagnostics"),
        ScopeRule(repo_root / "tmp/diagnostics", args.diag_days, "tmp/diagnostics"),
        ScopeRule(repo_root / "clients/python/packaging/temp", args.temp_days, "clients/python/packaging/temp"),
    ]

    env_snapshot = {
        "git_sha": _git_sha(repo_root),
        "timestamp_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_version": sys.version.replace("\n", " ").strip(),
        "platform": platform.platform(),
        "mode": "apply" if args.apply else "dry-run",
        "strict_gate": bool(args.strict_gate),
    }
    (artifact_dir / "env_snapshot.json").write_text(json.dumps(env_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    candidates = _collect_candidates(repo_root, rules, now)
    hard_violations: list[str] = []
    action_rows: list[dict[str, Any]] = []

    for row in candidates:
        candidate_path = repo_root / row["path"]
        tracked = _is_tracked(repo_root, candidate_path)
        action = "would_delete" if not args.apply else "deleted"
        if tracked:
            action = "blocked_tracked_file"
            hard_violations.append(f"tracked file candidate blocked: {row['path']}")
        elif args.apply:
            action = _delete_path(candidate_path)
        row["tracked"] = tracked
        row["action"] = action
        action_rows.append(row)

    with (artifact_dir / "retention_candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "size_bytes", "mtime_utc", "retention_days", "scope", "tracked", "action"],
        )
        writer.writeheader()
        writer.writerows(sorted(action_rows, key=lambda r: r["path"]))

    log_lines = [
        f"timestamp_utc={now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"mode={'apply' if args.apply else 'dry-run'}",
        f"candidates={len(action_rows)}",
        f"hard_violations={len(hard_violations)}",
    ]
    log_lines.extend(hard_violations)
    (artifact_dir / "retention_actions.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    hard_fail = len(hard_violations) > 0
    gate_result = "NO-GO" if hard_fail or (args.strict_gate and len(action_rows) > 0) else "GO"
    summary = {
        "result": gate_result,
        "mode": "apply" if args.apply else "dry-run",
        "strict_gate": bool(args.strict_gate),
        "counts": {
            "candidates": len(action_rows),
            "tracked_blocked": sum(1 for r in action_rows if r["tracked"]),
            "deleted": sum(1 for r in action_rows if str(r["action"]).startswith("deleted")),
            "would_delete": sum(1 for r in action_rows if r["action"] == "would_delete"),
        },
        "hard_violations": hard_violations,
        "missing_input": [
            str(rule.root.relative_to(repo_root)).replace("\\", "/")
            for rule in rules
            if not rule.root.exists()
        ],
    }
    (artifact_dir / "retention_audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (artifact_dir / "gate_result.txt").write_text(gate_result + "\n", encoding="utf-8")

    print(f"retention audit complete: mode={summary['mode']} candidates={len(action_rows)} result={gate_result}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
