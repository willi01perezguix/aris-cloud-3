from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_day6_docs_workflow_and_script_exist() -> None:
    expected = [
        "docs/ops/POST_GA_DAY6_HYPERCARE_CLOSEOUT.md",
        "docs/ops/HYPERCARE_ISSUES_AND_RESOLUTIONS.md",
        "docs/ops/INCIDENT_REPORTING_PLAYBOOK.md",
        "docs/ops/FINAL_PERFORMANCE_METRICS_DAY6.md",
        "docs/ops/FINAL_RELIABILITY_METRICS_DAY6.md",
        "runbooks/POST_GA_DAY6_STEADY_STATE_HANDOFF.md",
        "scripts/ops/post_ga_day6_closeout.py",
        ".github/workflows/post-ga-day6-closeout.yml",
    ]
    for rel in expected:
        assert (REPO_ROOT / rel).exists(), f"missing required file: {rel}"


def test_day6_workflow_contract() -> None:
    workflow = (REPO_ROOT / ".github/workflows/post-ga-day6-closeout.yml").read_text(encoding="utf-8")
    for marker in (
        "workflow_dispatch",
        "run_health_check",
        "run_final_tests",
        "publish_day6_artifacts",
        "if: always()",
        "if-no-files-found: error",
        "GO/NO-GO final certification",
    ):
        assert marker in workflow


def test_day6_closeout_script_outputs_artifacts() -> None:
    target = REPO_ROOT / "artifacts/post-ga/day6"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("final_save_delta.json", "final_arising_state.json", "save_metadata.txt"):
        p = target / name
        if p.exists():
            p.unlink()

    proc = subprocess.run(
        [sys.executable, "scripts/ops/post_ga_day6_closeout.py", "--artifact-dir", "artifacts/post-ga/day6", "--skip-aris-command"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    final_save_delta = json.loads((target / "final_save_delta.json").read_text(encoding="utf-8"))
    assert final_save_delta["version"] == "v1.0"
    assert final_save_delta["contract_drift"] is False
    assert final_save_delta["business_rule_drift"] is False
    assert (target / "final_arising_state.json").exists()
    assert (target / "save_metadata.txt").exists()
