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


def test_packaging_scripts_include_scaffold_markers() -> None:
    root = Path("clients/python/packaging")
    markers = ("pyinstaller", "build_summary.json", "venv", "artifact_prefix")

    for script_name in ("build_core.ps1", "build_control_center.ps1"):
        script = (root / script_name).read_text()
        for marker in markers:
            assert marker in script, f"{marker} missing in {script_name}"
