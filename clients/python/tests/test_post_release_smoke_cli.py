from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_smoke_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "post_release_smoke.py"
    spec = importlib.util.spec_from_file_location("post_release_smoke", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_post_release_smoke_cli_writes_json_and_log(tmp_path: Path) -> None:
    smoke = _load_smoke_module()
    rc = smoke.main([
        "--artifacts-dir",
        str(tmp_path),
        "--suite-name",
        "sdk_smoke_cli",
    ])

    assert rc == 0
    payload = json.loads((tmp_path / "post_release_smoke_result.json").read_text(encoding="utf-8"))
    assert payload["suite"] == "sdk_smoke_cli"
    assert payload["summary"]["ok"] is True
    log_text = (tmp_path / "post_release_smoke_result.log").read_text(encoding="utf-8")
    assert "overall=PASS" in log_text
