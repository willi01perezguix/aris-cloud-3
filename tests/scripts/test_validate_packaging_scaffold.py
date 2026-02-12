from __future__ import annotations

from pathlib import Path

from scripts.ci import validate_packaging_scaffold as validator


def _write(path: Path, content: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_valid_repo(tmp_path: Path) -> Path:
    packaging_root = tmp_path / "clients/python/packaging"
    for rel in validator.REQUIRED_PACKAGING_FILES:
        content = "ok\n"
        if rel in validator.REQUIRED_SCRIPT_MARKERS:
            markers = "\n".join(validator.REQUIRED_SCRIPT_MARKERS[rel])
            content = f"{markers}\n"
        _write(packaging_root / rel, content)

    for rel in validator.REQUIRED_CLIENT_PYPROJECTS:
        _write(tmp_path / rel, "[project]\nname='x'\nversion='0.1.0'\n")

    return tmp_path


def test_packaging_scaffold_happy_path(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)

    assert validator.validate_packaging_scaffold(repo) == []


def test_missing_packaging_file_fails_with_explicit_message(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)
    (repo / "clients/python/packaging/build_core.ps1").unlink()

    errors = validator.validate_packaging_scaffold(repo)

    assert any("Missing packaging scaffold file: clients/python/packaging/build_core.ps1" in err for err in errors)


def test_missing_pyproject_fails_with_explicit_message(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)
    (repo / "clients/python/aris_control_center_app/pyproject.toml").unlink()

    errors = validator.validate_packaging_scaffold(repo)

    assert any("Missing required client pyproject: clients/python/aris_control_center_app/pyproject.toml" in err for err in errors)


def test_missing_script_marker_fails_with_explicit_message(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)
    script_path = repo / "clients/python/packaging/build_core.ps1"
    script_path.write_text("build_summary.json\nvenv\n", encoding="utf-8")

    errors = validator.validate_packaging_scaffold(repo)

    assert any("Packaging scaffold script missing required marker 'artifact_prefix'" in err for err in errors)
