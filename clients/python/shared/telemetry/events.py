from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

TELEMETRY_CATEGORIES = {"auth", "navigation", "api_call_result", "error", "permission_denied"}
_FORBIDDEN_CONTEXT_KEYS = {
    "email",
    "password",
    "phone",
    "full_name",
    "address",
    "token",
    "authorization",
    "bank_name",
    "voucher_number",
    "card_number",
}


@dataclass(frozen=True)
class TelemetryEvent:
    category: str
    name: str
    module: str
    action: str
    timestamp_utc: str
    trace_id: str | None = None
    duration_ms: int | None = None
    success: bool | None = None
    error_code: str | None = None
    context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}


def _validate_context(context: dict[str, Any] | None) -> None:
    if not context:
        return
    illegal = sorted(key for key in context if key.lower() in _FORBIDDEN_CONTEXT_KEYS)
    if illegal:
        raise ValueError(f"PII-like keys are forbidden in telemetry context: {illegal}")


def build_event(
    *,
    category: str,
    name: str,
    module: str,
    action: str,
    trace_id: str | None = None,
    duration_ms: int | None = None,
    success: bool | None = None,
    error_code: str | None = None,
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> TelemetryEvent:
    if category not in TELEMETRY_CATEGORIES:
        raise ValueError(f"Unsupported telemetry category: {category}")
    _validate_context(context)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    return TelemetryEvent(
        category=category,
        name=name,
        module=module,
        action=action,
        timestamp_utc=stamp,
        trace_id=trace_id,
        duration_ms=duration_ms,
        success=success,
        error_code=error_code,
        context=context,
    )
