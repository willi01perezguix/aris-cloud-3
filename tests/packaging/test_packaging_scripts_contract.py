from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGING_ROOT = REPO_ROOT / "clients/python/packaging"


def _script_text(name: str) -> str:
    return (PACKAGING_ROOT / name).read_text(encoding="utf-8")


def test_build_scripts_support_required_params() -> None:
    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        text = _script_text(script_name)
        for token in ("$DryRun", "$CiMode", "$OutDir", "$VersionOverride"):
            assert token in text, f"{script_name} missing required parameter token {token}"


def test_build_scripts_include_preflight_checks() -> None:
    core_text = _script_text("build_core.ps1")
    cc_text = _script_text("build_control_center.ps1")

    assert "python executable not found in PATH" in core_text
    assert "expected entrypoint missing" in core_text
    assert "spec template missing" in core_text
    assert "output directory is not writable" in core_text

    assert "python executable not found in PATH" in cc_text
    assert "expected entrypoint missing" in cc_text
    assert "spec template missing" in cc_text
    assert "output directory is not writable" in cc_text


def test_dry_run_metadata_schema_keys_present() -> None:
    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        text = _script_text(script_name)
        for key in (
            "app_name",
            "version",
            "git_sha",
            "build_time_utc",
            "python_version",
            "os",
            "dry_run",
        ):
            assert re.search(rf"\b{re.escape(key)}\s*=", text), f"{script_name} missing metadata key '{key}'"




def test_outdir_path_normalization_contract() -> None:
    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        text = _script_text(script_name)

        assert "function Resolve-NormalizedPath" in text
        assert "[System.IO.Path]::IsPathRooted($Path)" in text
        assert "return [System.IO.Path]::GetFullPath($Path)" in text
        assert "return [System.IO.Path]::GetFullPath((Join-Path $Base $Path))" in text
        assert "Resolve-NormalizedPath -Path $targetOutDir -Base $root" in text


def test_no_duplicate_join_of_absolute_outdir() -> None:
    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        text = _script_text(script_name)

        assert "[System.IO.Path]::GetFullPath((Join-Path $root $targetOutDir))" not in text

def test_build_all_orchestrates_both_and_propagates_failures() -> None:
    text = _script_text("build_all.ps1")

    assert "./build_core.ps1" in text
    assert "./build_control_center.ps1" in text
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in text



def test_build_scripts_include_scaffold_runtime_markers() -> None:
    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        text = _script_text(script_name)

        assert "build_summary.json" in text
        assert "artifact_prefix" in text
        assert "venv is not active." in text
        assert "CI mode enabled; continuing." in text
        assert "Activate your venv before packaging." in text


def test_build_scripts_emit_summary_to_resolved_output_dir() -> None:
    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        text = _script_text(script_name)

        assert "$buildSummaryPath = Join-Path $resolvedOutDir \"build_summary.json\"" in text
        assert "$metadataPath = Join-Path $resolvedOutDir" in text
        assert "Resolved output directory:" in text


def test_build_scripts_log_deterministic_pyinstaller_command() -> None:
    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        text = _script_text(script_name)

        assert "$pyinstallerArgs = @(" in text
        assert "Write-Host \"Running: $pyinstallerCmd\"" in text
        assert "& pyinstaller @pyinstallerArgs" in text

def test_metadata_json_key_contract_fixture() -> None:
    metadata = {
        "app_name": "aris-core-3-app",
        "version": "0.0.0",
        "git_sha": "abcdef0",
        "build_time_utc": "2026-01-01T00:00:00Z",
        "python_version": "Python 3.11.9",
        "os": "windows",
        "dry_run": True,
    }

    payload = json.loads(json.dumps(metadata))

    assert set(payload.keys()) == {
        "app_name",
        "version",
        "git_sha",
        "build_time_utc",
        "python_version",
        "os",
        "dry_run",
    }
