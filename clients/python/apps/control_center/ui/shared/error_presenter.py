from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PresentedAdminError:
    category: str
    message: str
    safe_to_retry: bool
    details: dict[str, Any]

    def render(self, *, expanded: bool = False) -> dict[str, Any]:
        payload = {
            "category": self.category,
            "message": self.message,
            "safe_to_retry": self.safe_to_retry,
        }
        if expanded:
            payload["technical_details"] = self.details
        return payload


class AdminErrorPresenter:
    _CATEGORY_MESSAGES = {
        "validation": "Please correct the highlighted values and submit again.",
        "permission": "Your role does not allow this action.",
        "conflict": "This request conflicts with current system state.",
        "network": "Network issue detected. Retry when connectivity is stable.",
        "server": "Server error encountered. Retry in a moment or contact support.",
        "fatal": "A fatal error occurred. Please stop and review technical details.",
    }

    def present(
        self,
        *,
        message: str,
        action: str,
        code: str | None = None,
        trace_id: str | None = None,
        details: Any = None,
        allow_retry: bool = False,
        timestamp: datetime | None = None,
    ) -> PresentedAdminError:
        normalized_code = (code or self._extract_code(details) or "UNKNOWN").upper()
        category = self._categorize(message=message, details=details, code=normalized_code)
        safe_to_retry = allow_retry and category in {"network", "server"}
        return PresentedAdminError(
            category=category,
            message=self._CATEGORY_MESSAGES[category],
            safe_to_retry=safe_to_retry,
            details={
                "trace_id": trace_id,
                "code": normalized_code,
                "action": action,
                "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
                "raw": details,
            },
        )

    def _categorize(self, *, message: str, details: Any, code: str) -> str:
        probe = f"{message} {details} {code}".lower()
        if any(token in probe for token in {"validation", "invalid", "required", "format"}):
            return "validation"
        if any(token in probe for token in {"permission", "forbidden", "403", "denied"}):
            return "permission"
        if any(token in probe for token in {"conflict", "409", "already", "state"}):
            return "conflict"
        if any(token in probe for token in {"timeout", "network", "transport", "connection"}):
            return "network"
        if any(token in probe for token in {"500", "503", "server", "unavailable"}):
            return "server"
        return "fatal"

    @staticmethod
    def _extract_code(details: Any) -> str | None:
        if isinstance(details, dict) and details.get("code"):
            return str(details["code"])
        return None
