import json
from pathlib import Path

from app.main import create_app


def test_release_candidate_openapi_artifact_matches_runtime_contract():
    runtime_spec = create_app().openapi()
    artifact_path = Path("artifacts/release_candidate/openapi.json")
    artifact_spec = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_spec == runtime_spec


def test_non_canonical_pruned_openapi_file_is_not_present():
    assert not Path("docs/openapi-pruned.json").exists()
