from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except Exception:
        return "unknown"


def _exists(repo_root: Path, rel: str) -> bool:
    return (repo_root / rel).exists()


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-GA Day5 final certification gate")
    parser.add_argument("--artifact-dir", default="artifacts/post-ga/day5")
    parser.add_argument("--strict-gate", action="store_true", default=False)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    artifact_dir = repo_root / args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    required_docs = [
        "docs/ops/POST_GA_DAY5_FINAL_CERTIFICATION.md",
        "docs/ops/V1_RELEASE_FREEZE_BASELINE.md",
        "docs/ops/V1_1_CHANGE_INTAKE_POLICY.md",
        "docs/ops/V1_FREEZE_MANIFEST.yaml",
        "runbooks/OPS_30_60_90_PLAN.md",
        "runbooks/ONCALL_OWNERSHIP_MATRIX_v1.md",
        "artifacts/post-ga/day5/certification_manifest.json",
        ".github/workflows/post-ga-day5-certification.yml",
    ]

    expected_evidence = [
        "artifacts/release_candidate/openapi.json",
        "artifacts/release_candidate/test_matrix_summary.json",
        "artifacts/release_candidate/security_gate_summary.json",
        "artifacts/release_candidate/backup_restore_drill_report.json",
        "docs/releases/GA_RELEASE_MANIFEST.json",
    ]

    missing_docs = [rel for rel in required_docs if not _exists(repo_root, rel)]
    present_evidence = [rel for rel in expected_evidence if _exists(repo_root, rel)]
    missing_evidence = [rel for rel in expected_evidence if rel not in present_evidence]

    gate_path = artifact_dir / "certification_gate_result.txt"
    prior_gate = _read_text_if_exists(gate_path)

    reliability = {
        "timestamp_utc": _utc_now(),
        "required_docs_present": len(required_docs) - len(missing_docs),
        "required_docs_total": len(required_docs),
        "evidence_present": len(present_evidence),
        "evidence_total": len(expected_evidence),
        "missing_docs": missing_docs,
        "missing_evidence": missing_evidence,
        "status": "incomplete evidence" if missing_docs or missing_evidence else "complete",
    }

    recovery = {
        "timestamp_utc": _utc_now(),
        "backup_restore_evidence_present": _exists(repo_root, "artifacts/release_candidate/backup_restore_drill_report.json"),
        "runbook_present": _exists(repo_root, "runbooks/OPS_30_60_90_PLAN.md"),
        "oncall_matrix_present": _exists(repo_root, "runbooks/ONCALL_OWNERSHIP_MATRIX_v1.md"),
        "status": "ready" if _exists(repo_root, "artifacts/release_candidate/backup_restore_drill_report.json") else "incomplete evidence",
    }

    environment = {
        "timestamp_utc": _utc_now(),
        "git_sha": _git_sha(repo_root),
        "python_version": sys.version.replace("\n", " ").strip(),
        "platform": platform.platform(),
        "strict_gate": bool(args.strict_gate),
        "previous_gate_result": prior_gate or "none",
    }

    hard_fail = bool(missing_docs)
    incomplete_evidence = bool(missing_evidence)

    if hard_fail:
        gate_result = "NO-GO"
    elif incomplete_evidence:
        gate_result = "INCOMPLETE EVIDENCE"
    else:
        gate_result = "GO"

    (artifact_dir / "reliability_summary.json").write_text(json.dumps(reliability, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (artifact_dir / "recovery_readiness.json").write_text(json.dumps(recovery, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (artifact_dir / "environment_fingerprint.json").write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate_path.write_text(gate_result + "\n", encoding="utf-8")

    print(f"post-ga day5 certification: result={gate_result} strict_gate={args.strict_gate}")
    if missing_docs:
        print("missing required docs:")
        for rel in missing_docs:
            print(f"- {rel}")
    if missing_evidence:
        print("incomplete evidence:")
        for rel in missing_evidence:
            print(f"- {rel}")

    return 1 if args.strict_gate and (hard_fail or incomplete_evidence) else 0


if __name__ == "__main__":
    raise SystemExit(main())
