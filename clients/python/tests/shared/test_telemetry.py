from __future__ import annotations

import io
import json

import pytest

from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger


def test_build_event_validates_category() -> None:
    with pytest.raises(ValueError):
        build_event(category="unknown", name="n", module="core_app", action="a")


def test_build_event_blocks_pii_context_keys() -> None:
    with pytest.raises(ValueError):
        build_event(
            category="auth",
            name="login_attempt",
            module="core_app",
            action="submit",
            context={"email": "user@example.com"},
        )


def test_logger_writes_local_file_and_stdout(tmp_path) -> None:
    stream = io.StringIO()
    logger = TelemetryLogger(
        app_name="core_app",
        enabled=True,
        log_file=tmp_path / "telemetry.jsonl",
        stdout_sink=True,
        stdout_stream=stream,
    )
    event = build_event(category="navigation", name="stock_open", module="core_app", action="open_screen")

    assert logger.emit(event) is True

    written = (tmp_path / "telemetry.jsonl").read_text().strip().splitlines()
    assert len(written) == 1
    payload = json.loads(written[0])
    assert payload["category"] == "navigation"
    assert payload["app_name"] == "core_app"
    assert "stock_open" in stream.getvalue()


def test_logger_respects_disabled_toggle(tmp_path) -> None:
    logger = TelemetryLogger(app_name="core_app", enabled=False, log_file=tmp_path / "telemetry.jsonl")
    event = build_event(category="error", name="request_failed", module="sdk", action="fetch")

    assert logger.emit(event) is False
    assert not (tmp_path / "telemetry.jsonl").exists()
