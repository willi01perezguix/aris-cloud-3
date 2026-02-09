from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Mapping

TRACE_HEADER = "X-Trace-ID"


@dataclass
class TraceContext:
    trace_id: str | None = None

    def ensure(self) -> str:
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())
        return self.trace_id

    def update_from_headers(self, headers: Mapping[str, str]) -> None:
        trace_id = headers.get(TRACE_HEADER)
        if trace_id:
            self.trace_id = trace_id

    def update_from_payload(self, payload: Mapping[str, object]) -> None:
        trace_id = payload.get("trace_id")
        if isinstance(trace_id, str) and trace_id:
            self.trace_id = trace_id
