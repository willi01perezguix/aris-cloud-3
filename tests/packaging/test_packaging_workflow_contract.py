from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / '.github/workflows/clients-packaging-smoke.yml'


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding='utf-8')


def test_workflow_prepares_expected_diagnostics_directories() -> None:
    text = _workflow_text()

    assert 'PACKAGING_ARTIFACTS_DIR: clients/python/packaging/temp/artifacts' in text
    assert 'New-Item -ItemType Directory -Path "$env:PACKAGING_ARTIFACTS_DIR/core" -Force | Out-Null' in text
    assert 'New-Item -ItemType Directory -Path "$env:PACKAGING_ARTIFACTS_DIR/control_center" -Force | Out-Null' in text


def test_workflow_persists_tree_and_dryrun_logs() -> None:
    text = _workflow_text()

    assert '_tree_before_smoke.txt' in text
    assert '_tree_after_smoke.txt' in text
    assert 'build_core_dryrun.log' in text
    assert 'build_control_center_dryrun.log' in text
    assert 'build_core_exit_code.txt' in text
    assert 'build_control_center_exit_code.txt' in text


def test_workflow_always_uploads_diagnostics_with_warning_mode() -> None:
    text = _workflow_text()

    assert '- name: Upload packaging smoke diagnostics' in text
    assert 'if: always()' in text
    assert 'if-no-files-found: warn' in text


def test_workflow_has_final_gate_on_smoke_step_outcomes() -> None:
    text = _workflow_text()

    assert '- name: Gate dry-run smoke results' in text
    assert 'steps.core_smoke.outcome' in text
    assert 'steps.control_center_smoke.outcome' in text
    assert 'Packaging dry-run smoke failed' in text
