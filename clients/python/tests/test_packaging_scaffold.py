from __future__ import annotations

from pathlib import Path


def test_packaging_files_exist() -> None:
    root = Path("clients/python/packaging")
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
    root = Path("clients/python/packaging")
    assert "DryRun" in (root / "build_core.ps1").read_text()
    assert "DryRun" in (root / "build_control_center.ps1").read_text()


def test_build_scripts_include_preflight_checks() -> None:
    root = Path("clients/python/packaging")
    script = (root / "build_core.ps1").read_text()
    assert "entrypoint" in script
    assert "build_summary.json" in script


def test_build_scripts_include_runtime_checks() -> None:
    root = Path("clients/python/packaging")
    script = (root / "build_control_center.ps1").read_text()
    assert "pyinstaller" in script
    assert "venv" in script
    assert "artifact_prefix" in script
