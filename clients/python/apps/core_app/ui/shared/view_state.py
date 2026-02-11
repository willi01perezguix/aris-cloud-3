from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ViewStateStatus(str, Enum):
    LOADING = "loading"
    EMPTY = "empty"
    SUCCESS = "success"
    PARTIAL_ERROR = "partial_error"
    FATAL_ERROR = "fatal_error"
    NO_PERMISSION = "no_permission"


@dataclass(frozen=True)
class ViewState:
    status: ViewStateStatus
    message: str | None = None
    trace_id: str | None = None
    data_available: bool = False

    def render(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "trace_id": self.trace_id,
            "data_available": self.data_available,
        }


def resolve_state(
    *,
    can_view: bool,
    is_loading: bool,
    error: str | None,
    has_data: bool,
    trace_id: str | None = None,
) -> ViewState:
    if not can_view:
        return ViewState(ViewStateStatus.NO_PERMISSION, "Access denied", trace_id=trace_id)
    if is_loading:
        return ViewState(ViewStateStatus.LOADING, "Loading data...", trace_id=trace_id, data_available=has_data)
    if error and has_data:
        return ViewState(ViewStateStatus.PARTIAL_ERROR, error, trace_id=trace_id, data_available=True)
    if error:
        return ViewState(ViewStateStatus.FATAL_ERROR, error, trace_id=trace_id)
    if not has_data:
        return ViewState(ViewStateStatus.EMPTY, "No data found", trace_id=trace_id)
    return ViewState(ViewStateStatus.SUCCESS, "Ready", trace_id=trace_id, data_available=True)
