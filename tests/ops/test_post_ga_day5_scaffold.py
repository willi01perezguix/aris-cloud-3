from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_day5_docs_scripts_workflow_exist() -> None:
    expected = [
        "docs/ops/POST_GA_DAY5_FINAL_CERTIFICATION.md",
        "docs/ops/V1_RELEASE_FREEZE_BASELINE.md",
        "docs/ops/V1_1_CHANGE_INTAKE_POLICY.md",
        "docs/ops/V1_FREEZE_MANIFEST.yaml",
        "runbooks/OPS_30_60_90_PLAN.md",
        "runbooks/ONCALL_OWNERSHIP_MATRIX_v1.md",
        "artifacts/post-ga/day5/certification_manifest.json",
        "scripts/ops/post_ga_day5_certify.py",
        "scripts/ops/post_ga_day5_certify.sh",
        "scripts/ops/post_ga_day5_certify.ps1",
        ".github/workflows/post-ga-day5-certification.yml",
    ]
    for rel in expected:
        assert (REPO_ROOT / rel).exists(), f"missing required file: {rel}"


def test_day5_workflow_contract() -> None:
    workflow = (REPO_ROOT / ".github/workflows/post-ga-day5-certification.yml").read_text(encoding="utf-8")
    for marker in (
        "workflow_dispatch",
        "strict_gate",
        "run_full_suite",
        "publish_day5_artifacts",
        "if: always()",
        "if-no-files-found: error",
    ):
        assert marker in workflow


def test_day5_certification_default_outputs() -> None:
    target = REPO_ROOT / "artifacts/post-ga/day5"
    target.mkdir(parents=True, exist_ok=True)
    for name in (
        "reliability_summary.json",
        "recovery_readiness.json",
        "environment_fingerprint.json",
        "certification_gate_result.txt",
    ):
        p = target / name
        if p.exists():
            p.unlink()

    proc = subprocess.run(
        [sys.executable, "scripts/ops/post_ga_day5_certify.py", "--artifact-dir", "artifacts/post-ga/day5"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    reliability = json.loads((target / "reliability_summary.json").read_text(encoding="utf-8"))
    assert reliability["status"] in {"complete", "incomplete evidence"}
    assert (target / "recovery_readiness.json").exists()
    assert (target / "environment_fingerprint.json").exists()
    assert (target / "certification_gate_result.txt").exists()


def test_day5_strict_gate_semantics() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/ops/post_ga_day5_certify.py",
            "--artifact-dir",
            "artifacts/post-ga/day5",
            "--strict-gate",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    gate_result = (REPO_ROOT / "artifacts/post-ga/day5/certification_gate_result.txt").read_text(encoding="utf-8").strip()
    if gate_result == "GO":
        assert proc.returncode == 0
    else:
        assert proc.returncode != 0
