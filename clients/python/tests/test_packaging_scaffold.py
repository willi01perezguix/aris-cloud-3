from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return next(
        (x for x in Path(__file__).resolve().parents if (x / ".github" / "workflows").exists()),
        Path(__file__).resolve().parent,
    )


def _packaging_root() -> Path:
    return _repo_root() / "clients" / "python" / "packaging"


def test_packaging_files_exist() -> None:
    root = _packaging_root()
    expected = [
        "core_app.spec.template",
        "control_center.spec.template",
        "build_core.bat",
        "build_core.ps1",
        "build_control_center.bat",
        "build_control_center.ps1",
        "version.json",
        "README.md",
        "build_all.ps1",
        "installer_placeholder.ps1",
    ]
    for name in expected:
        assert (root / name).exists(), f"missing {name}"


def test_powershell_scripts_support_dry_run() -> None:
    root = _packaging_root()
    assert "DryRun" in (root / "build_core.ps1").read_text()
    assert "DryRun" in (root / "build_control_center.ps1").read_text()


def test_packaging_scripts_include_scaffold_markers() -> None:
    root = _packaging_root()
    script_markers = {
        "build_core.ps1": (
            "Set-StrictMode -Version Latest",
            "$PSNativeCommandUseErrorActionPreference = $true",
            "pyinstaller",
            "build_summary.json",
            "venv",
            "artifact_prefix",
            "dist directory is empty",
        ),
        "build_control_center.ps1": (
            "Set-StrictMode -Version Latest",
            "$PSNativeCommandUseErrorActionPreference = $true",
            "pyinstaller",
            "build_summary.json",
            "venv",
            "artifact_prefix",
            "dist directory is empty",
        ),
        "build_all.ps1": (
            "Set-StrictMode -Version Latest",
            "$PSNativeCommandUseErrorActionPreference = $true",
            "build_core.ps1",
            "build_control_center.ps1",
        ),
    }

    for script_name, markers in script_markers.items():
        script = (root / script_name).read_text()
        for marker in markers:
            assert marker in script, f"{marker} missing in {script_name}"


def test_windows_packaging_smoke_workflow_uploads_diagnostics_always() -> None:
    repo_root = _repo_root()
    workflow_path = repo_root / ".github" / "workflows" / "clients-packaging-smoke.yml"
    assert workflow_path.exists(), f"Missing workflow file: {workflow_path}"

    workflow = workflow_path.read_text(encoding="utf-8")

    assert "PACKAGING_RUNNER_ARTIFACTS_DIR" in workflow
    assert "if-no-files-found: error" in workflow
    assert "if: always()" in workflow
    assert "step_outcomes.txt" in workflow
