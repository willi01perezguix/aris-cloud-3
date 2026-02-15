from __future__ import annotations

from pathlib import Path

import aris3_client_sdk

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python >=3.11 in CI
    import tomli as tomllib


def test_sdk_version_matches_pyproject_metadata() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "aris3_client_sdk" / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    assert aris3_client_sdk.__version__ == project["version"]
