from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class OperationRecord:
    actor: str
    target: str
    action: str
    at: datetime
    trace_id: str | None = None
    idempotency_key: str | None = None
    transaction_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    actor: str | None = None
    tenant_id: str | None = None
    allowed_permissions: set[str] = field(default_factory=set)
    operations: list[OperationRecord] = field(default_factory=list)

    def add_operation(self, operation: OperationRecord) -> None:
        self.operations.insert(0, operation)
        del self.operations[30:]


@dataclass
class ControlCenterState:
    session: SessionState = field(default_factory=SessionState)
    selected_user_id: str | None = None
    selected_store_id: str | None = None
