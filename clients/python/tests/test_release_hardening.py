from __future__ import annotations

import json
import zipfile
from pathlib import Path

from aris3_client_sdk.config import load_config
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.ui_errors import to_user_facing_error
from create_support_bundle import create_bundle
from packaging_verify import verify_packaging
from qa_matrix_runner import ScenarioResult, should_fail, summarize
from release_tools import manifest_payload, redact_text


def test_timeout_retry_config_parsing(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ARIS3_CONNECT_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("ARIS3_READ_TIMEOUT_SECONDS", "9")
    monkeypatch.setenv("ARIS3_RETRIES", "4")
    cfg = load_config()
    assert cfg.connect_timeout_seconds == 2.0
    assert cfg.read_timeout_seconds == 9.0
    assert cfg.retries == 4


def test_error_display_model_includes_trace_id() -> None:
    err = ApiError(code="X", message="boom", details={"f": 1}, trace_id="trace-1", status_code=500)
    display = to_user_facing_error(err)
    assert display.message == "boom"
    assert display.trace_id == "trace-1"


def test_support_redaction_logic() -> None:
    text, count = redact_text("token=abc password:xyz safe=1")
    assert "<REDACTED>" in text
    assert count == 2


def test_qa_matrix_aggregation_logic() -> None:
    results = [ScenarioResult("a", "PASS", "ok"), ScenarioResult("b", "FAIL", "x"), ScenarioResult("c", "SKIP", "y")]
    summary = summarize(results)
    assert summary["counts"] == {"PASS": 1, "FAIL": 1, "SKIP": 1}
    assert should_fail(results, "critical") is True


def test_packaging_manifest_generation_logic(tmp_path: Path) -> None:
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"exe")
    manifest = manifest_payload("core", "1.0.0", [exe])
    assert manifest["files"][0]["size"] == 3


def test_retry_policy_safe_methods_only(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    cfg = load_config()
    http = HttpClient(cfg)
    adapter = http.session.get_adapter("https://")
    retries = adapter.max_retries
    assert "GET" in retries.allowed_methods
    assert "POST" not in retries.allowed_methods


def test_support_bundle_creation_excludes_plain_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ARIS3_TOKEN", "secret-value")
    bundle = create_bundle(tmp_path)
    with zipfile.ZipFile(bundle) as zf:
        metadata = json.loads(zf.read("metadata.json"))
        profile = zf.read("env_profile.json").decode("utf-8")
    assert metadata["redaction_applied"] is True
    assert "secret-value" not in profile


def test_packaging_verify_report_generation(tmp_path: Path) -> None:
    root = tmp_path / "packaging"
    (root / "dist").mkdir(parents=True)
    (root / "version.json").write_text('{"version":"1.0.0"}')
    (tmp_path / "aris_core_3_app/src/aris_core_3_app").mkdir(parents=True)
    (tmp_path / "aris_core_3_app/src/aris_core_3_app/app.py").write_text("x")
    (tmp_path / "aris_control_center_app/src/aris_control_center_app").mkdir(parents=True)
    (tmp_path / "aris_control_center_app/src/aris_control_center_app/app.py").write_text("x")
    (tmp_path / ".env.example").write_text("ARIS3_API_BASE_URL=")
    manifest, report = verify_packaging(root, "1.0.0")
    assert manifest.exists()
    assert report.exists()
