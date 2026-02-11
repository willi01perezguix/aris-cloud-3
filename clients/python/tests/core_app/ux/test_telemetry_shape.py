from __future__ import annotations

import json
from pathlib import Path

from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger


def test_telemetry_event_shape_is_non_pii(tmp_path: Path) -> None:
    logger = TelemetryLogger(app_name="core_app", enabled=True, log_file=tmp_path / "telemetry.jsonl")
    event = build_event(
        category="api_call_result",
        name="api_call_result",
        module="stock",
        action="stock_list.load",
        trace_id="trace-1",
        duration_ms=8,
        success=False,
        error_code="timeout",
        context={"module": "stock", "action": "load"},
    )

    emitted = logger.emit(event)

    payload = json.loads((tmp_path / "telemetry.jsonl").read_text().strip())
    assert emitted is True
    assert payload["name"] == "api_call_result"
    assert "password" not in payload.get("context", {})
