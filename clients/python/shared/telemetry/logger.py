from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TextIO

from .events import TelemetryEvent


class TelemetryLogger:
    def __init__(
        self,
        *,
        app_name: str,
        enabled: bool | None = None,
        log_file: str | Path | None = None,
        stdout_sink: bool = False,
        stdout_stream: TextIO | None = None,
    ) -> None:
        self.app_name = app_name
        self.enabled = enabled if enabled is not None else _env_telemetry_enabled()
        self.log_file = Path(log_file) if log_file else Path("artifacts") / "telemetry" / f"{app_name}.jsonl"
        self.stdout_sink = stdout_sink
        self.stdout_stream = stdout_stream

    def emit(self, event: TelemetryEvent) -> bool:
        if not self.enabled:
            return False

        payload = event.to_dict()
        payload["app_name"] = self.app_name
        line = json.dumps(payload, sort_keys=True)

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as fp:
            fp.write(f"{line}\n")

        if self.stdout_sink:
            stream = self.stdout_stream or os.sys.stdout
            stream.write(f"{line}\n")
            stream.flush()

        return True


def _env_telemetry_enabled() -> bool:
    value = os.getenv("ARIS3_TELEMETRY_ENABLED", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}
