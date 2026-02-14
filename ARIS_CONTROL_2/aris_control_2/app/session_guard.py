from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from aris_control_2.app.state import SessionState


@dataclass(frozen=True)
class SessionValidation:
    valid: bool
    reason: str | None = None


def validate_token(token: str | None, now_utc: datetime | None = None) -> SessionValidation:
    if not token:
        return SessionValidation(valid=False, reason="missing_token")

    parts = token.split(".")
    if len(parts) != 3:
        return SessionValidation(valid=False, reason="corrupt_token")

    payload_part = parts[1]
    padded = payload_part + ("=" * (-len(payload_part) % 4))
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, UnicodeDecodeError):
        return SessionValidation(valid=False, reason="corrupt_token")

    exp = payload.get("exp")
    if exp is None:
        return SessionValidation(valid=True)

    if not isinstance(exp, (int, float)):
        return SessionValidation(valid=False, reason="corrupt_token")

    now = now_utc or datetime.now(tz=timezone.utc)
    if float(exp) <= now.timestamp():
        return SessionValidation(valid=False, reason="expired_token")

    return SessionValidation(valid=True)


class SessionGuard:
    def __init__(self, on_invalid_session: Callable[[str], None]) -> None:
        self._on_invalid_session = on_invalid_session

    def require_session(self, session: SessionState, module: str) -> bool:
        session.current_module = module
        validation = validate_token(session.access_token)
        if validation.valid:
            return True

        self._on_invalid_session(validation.reason or "invalid_session")
        return False
