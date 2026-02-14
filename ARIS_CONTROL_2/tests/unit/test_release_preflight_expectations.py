from pathlib import Path


def test_preflight_script_contains_required_checks() -> None:
    script = Path("scripts/windows/preflight_release.ps1").read_text(encoding="utf-8")

    assert "git branch --show-current" in script
    assert "git status --porcelain" in script
    assert "git check-ignore .env" in script
    assert ".env.example" in script
    assert "out\\exports" in script
    assert "run_control_center_dev.ps1" in script
    assert "build_control_center.ps1" in script


def test_smoke_script_contains_release_commands() -> None:
    script = Path("scripts/windows/smoke_release.ps1").read_text(encoding="utf-8")

    assert "pytest -q" in script
    assert "run_control_center_dev.ps1" in script
    assert "build_control_center.ps1" in script
    assert "dist\\ARIS_CONTROL_2.exe" in script
    assert "Get-FileHash" in script
