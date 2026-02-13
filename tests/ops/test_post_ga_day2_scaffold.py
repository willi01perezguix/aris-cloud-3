from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_day2_docs_and_manifests_exist() -> None:
    expected = [
        "docs/ops/POST_GA_DAY2_PERFORMANCE_BASELINE.md",
        "docs/ops/SLI_SLO_ERROR_BUDGET_v1.md",
        "runbooks/ALERT_THRESHOLDS_AND_ESCALATION_v1.md",
        "docs/ops/BASELINE_MANIFEST_DAY2.json",
        "docs/ops/ERROR_BUDGET_POLICY_DAY2.json",
    ]
    for rel in expected:
        assert (REPO_ROOT / rel).exists(), f"missing required file: {rel}"


def test_day2_scripts_and_workflow_contract() -> None:
    sh_script = (REPO_ROOT / "scripts/ops/post_ga_day2_baseline.sh").read_text(encoding="utf-8")
    ps1_script = (REPO_ROOT / "scripts/ops/post_ga_day2_baseline.ps1").read_text(encoding="utf-8")
    perf_script = (REPO_ROOT / "scripts/ops/perf_snapshot.py").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/post-ga-day2-performance.yml").read_text(encoding="utf-8")

    assert "artifacts/post-ga/day2" in sh_script
    assert "artifacts/post-ga/day2" in ps1_script
    assert "metadata.json" in perf_script
    assert "pytest_durations_summary.json" in perf_script

    assert "workflow_dispatch" in workflow
    assert "run_full_suite" in workflow
    assert "if: always()" in workflow
    assert "if-no-files-found: error" in workflow
