from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_day4_docs_scripts_workflow_exist() -> None:
    expected = [
        "docs/ops/POST_GA_DAY4_COST_PERFORMANCE_GOVERNANCE.md",
        "docs/ops/COST_BUDGETS_AND_THRESHOLDS_v1.md",
        "docs/ops/PERFORMANCE_BUDGETS_v1.md",
        "docs/ops/RETENTION_POLICY_v1.md",
        "docs/ops/COST_PERF_BASELINE_DAY4.json",
        "scripts/ops/post_ga_day4_retention_audit.py",
        "scripts/ops/post_ga_day4_retention_audit.sh",
        "scripts/ops/post_ga_day4_retention_audit.ps1",
        "scripts/ops/cost_perf_snapshot.py",
        "runbooks/ONCALL_HANDOFF_FINAL_v1.md",
        "runbooks/SEV_TRIAGE_MATRIX_v1.md",
        "docs/ops/POST_GA_HANDOFF_CHECKLIST_DAY4.md",
        ".github/workflows/post-ga-day4-governance.yml",
    ]
    for rel in expected:
        assert (REPO_ROOT / rel).exists(), f"missing required file: {rel}"


def test_day4_workflow_contract() -> None:
    workflow = (REPO_ROOT / ".github/workflows/post-ga-day4-governance.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in workflow
    assert "strict_gate" in workflow
    assert "apply_cleanup" in workflow
    assert "run_full_suite" in workflow
    assert "if: always()" in workflow
    assert "if-no-files-found: error" in workflow


def test_retention_dry_run_default(tmp_path: Path) -> None:
    target = REPO_ROOT / "artifacts/post-ga/day4"
    if target.exists():
        for f in target.glob("*"):
            if f.is_file():
                f.unlink()

    proc = subprocess.run(
        [sys.executable, "scripts/ops/post_ga_day4_retention_audit.py", "--artifact-dir", "artifacts/post-ga/day4"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    summary = json.loads((REPO_ROOT / "artifacts/post-ga/day4/retention_audit_summary.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "dry-run"
    assert (REPO_ROOT / "artifacts/post-ga/day4/gate_result.txt").exists()
