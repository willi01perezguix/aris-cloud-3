from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class AdminViewStatus(str, Enum):
    LOADING = "loading"
    EMPTY = "empty"
    SUCCESS = "success"
    NO_PERMISSION = "no_permission"
    FATAL = "fatal"


@dataclass(frozen=True)
class AdminViewState:
    status: AdminViewStatus
    message: str
    trace_id: str | None = None

    def render(self) -> dict[str, Any]:
        return {"status": self.status.value, "message": self.message, "trace_id": self.trace_id}


def resolve_admin_view_state(*, can_view: bool, loading: bool, has_data: bool, error: str | None, trace_id: str | None = None) -> AdminViewState:
    if not can_view:
        return AdminViewState(status=AdminViewStatus.NO_PERMISSION, message="Access denied", trace_id=trace_id)
    if loading:
        return AdminViewState(status=AdminViewStatus.LOADING, message="Loading", trace_id=trace_id)
    if error and not has_data:
        return AdminViewState(status=AdminViewStatus.FATAL, message=error, trace_id=trace_id)
    if not has_data:
        return AdminViewState(status=AdminViewStatus.EMPTY, message="No records", trace_id=trace_id)
    return AdminViewState(status=AdminViewStatus.SUCCESS, message="Ready", trace_id=trace_id)
