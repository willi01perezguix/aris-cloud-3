from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PresentedError:
    category: str
    user_message: str
    safe_to_retry: bool
    code: str
    details: dict[str, Any]


class ErrorPresenter:
    """Maps backend/client failures to consistent UX-friendly payloads."""

    _CATEGORY_MESSAGES = {
        "validation": "Please review the highlighted fields and try again.",
        "permission_denied": "You do not have permission to perform this action.",
        "conflict": "This action cannot be completed in the current state.",
        "not_found": "The requested record was not found.",
        "transport": "Temporary connectivity issue. Please retry.",
        "server": "Service error. Try again shortly or contact support.",
        "unknown": "Unexpected error. Please try again.",
    }

    def present(
        self,
        *,
        message: str,
        details: Any = None,
        trace_id: str | None = None,
        action: str,
        code: str | None = None,
        allow_retry: bool = False,
    ) -> PresentedError:
        normalized_code = (code or self._extract_code(details) or "UNKNOWN").upper()
        category = self._categorize(message=message, details=details, code=normalized_code)
        safe_to_retry = allow_retry and category in {"transport", "server"}
        technical = {
            "code": normalized_code,
            "trace_id": trace_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_details": details,
        }
        return PresentedError(
            category=category,
            user_message=self._CATEGORY_MESSAGES[category],
            safe_to_retry=safe_to_retry,
            code=normalized_code,
            details=technical,
        )

    def _categorize(self, *, message: str, details: Any, code: str) -> str:
        probe = f"{message} {details} {code}".lower()
        if any(token in probe for token in {"validation", "invalid", "required", "qty", "format"}):
            return "validation"
        if any(token in probe for token in {"permission", "forbidden", "denied", "403"}):
            return "permission_denied"
        if any(token in probe for token in {"conflict", "already", "state", "409"}):
            return "conflict"
        if any(token in probe for token in {"not found", "404", "missing record"}):
            return "not_found"
        if any(token in probe for token in {"timeout", "network", "connection", "transport", "tempor"}):
            return "transport"
        if any(token in probe for token in {"500", "503", "server", "internal error", "unavailable"}):
            return "server"
        return "unknown"

    @staticmethod
    def _extract_code(details: Any) -> str | None:
        if isinstance(details, dict):
            raw = details.get("code")
            return str(raw) if raw else None
        return None
