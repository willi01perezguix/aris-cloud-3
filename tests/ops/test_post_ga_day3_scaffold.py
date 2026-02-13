from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_day3_docs_and_manifests_exist() -> None:
    expected = [
        "docs/ops/POST_GA_DAY3_CAPACITY_CHARACTERIZATION.md",
        "docs/ops/CAPACITY_GUARDRAILS_v1.md",
        "runbooks/DEGRADATION_AND_RECOVERY_PLAYBOOK_v1.md",
        "docs/ops/OBSERVABILITY_HARDENING_DAY3.md",
        "docs/ops/ALERT_CATALOG_DAY3.json",
        "docs/ops/SERVICE_LEVEL_DASHBOARD_SPEC_DAY3.md",
    ]
    for rel in expected:
        assert (REPO_ROOT / rel).exists(), f"missing required file: {rel}"


def test_day3_scripts_and_workflow_contract() -> None:
    sh_script = (REPO_ROOT / "scripts/ops/post_ga_day3_load_probe.sh").read_text(encoding="utf-8")
    ps1_script = (REPO_ROOT / "scripts/ops/post_ga_day3_load_probe.ps1").read_text(encoding="utf-8")
    probe_script = (REPO_ROOT / "scripts/ops/load_probe.py").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/post-ga-day3-load-observability.yml").read_text(encoding="utf-8")

    assert "artifacts/post-ga/day3" in sh_script
    assert "artifacts/post-ga/day3" in ps1_script

    assert "summary.json" in probe_script
    assert "timings.csv" in probe_script
    assert "env_snapshot.json" in probe_script
    assert "gate_result.txt" in probe_script
    assert "--iterations" in probe_script
    assert "--concurrency" in probe_script
    assert "--warmup" in probe_script
    assert "--timeout-seconds" in probe_script
    assert "--strict-gate" in probe_script

    assert "workflow_dispatch" in workflow
    assert "profile" in workflow
    assert "strict_gate" in workflow
    assert "run_full_suite" in workflow
    assert "if: always()" in workflow
    assert "if-no-files-found: error" in workflow
