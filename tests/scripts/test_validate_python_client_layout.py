from __future__ import annotations

from pathlib import Path

from scripts.ci import validate_python_client_layout as validator


WORKFLOW_TEMPLATE = """name: test\nsteps:\n  - run: pip install -e ./clients/python/aris3_client_sdk\n"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_valid_repo(tmp_path: Path) -> Path:
    for rel in validator.REQUIRED_SUBPROJECTS:
        _write(tmp_path / rel / "pyproject.toml", "[project]\nname='x'\nversion='0.1.0'\n")

    _write(
        tmp_path / "clients/python/requirements.txt",
        "\n".join(sorted(validator.ALLOWED_CLIENT_EDITABLES)) + "\n",
    )
    _write(tmp_path / "requirements.txt", "pytest==8.3.3\n")
    _write(tmp_path / ".github/workflows/ci.yml", WORKFLOW_TEMPLATE)
    return tmp_path


def test_happy_path(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)
    assert validator.run_validation(repo) == []


def test_missing_pyproject_detected(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)
    (repo / "clients/python/aris_core_3_app/pyproject.toml").unlink()

    errors = validator.run_validation(repo)

    assert any("Missing required pyproject.toml" in error for error in errors)


def test_blocked_workflow_pattern_detected(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)
    _write(
        repo / ".github/workflows/clients.yml",
        "name: bad\nsteps:\n  - run: pip install -e aris3_client_sdk[dev]\n",
    )

    errors = validator.run_validation(repo)

    assert any("blocked pattern 'aris3_client_sdk[dev]'" in error for error in errors)


def test_invalid_requirements_editable_detected(tmp_path: Path) -> None:
    repo = _seed_valid_repo(tmp_path)
    _write(
        repo / "clients/python/requirements.txt",
        "-e ./aris3_client_sdk\n-e ./not_real_client\n",
    )

    errors = validator.run_validation(repo)

    assert any("unsupported editable target" in error for error in errors)
