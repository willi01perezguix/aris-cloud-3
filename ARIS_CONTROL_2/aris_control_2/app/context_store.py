from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONTEXT_FILE = Path.home() / ".aris_control_2_operator_context.json"
DEFAULT_RECOVERY_FILE = Path.home() / ".aris_control_2_auth_recovery_context.json"


def _context_path() -> Path:
    configured = os.getenv("ARIS3_OPERATOR_CONTEXT_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_CONTEXT_FILE


def _recovery_path() -> Path:
    configured = os.getenv("ARIS3_AUTH_RECOVERY_CONTEXT_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_RECOVERY_FILE


def load_context() -> dict[str, Any]:
    path = _context_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (ValueError, OSError):
        return {}


def save_context(
    *,
    session_fingerprint: str,
    selected_tenant_id: str | None,
    filters_by_module: dict[str, dict[str, str]],
    pagination_by_module: dict[str, dict[str, int]],
) -> None:
    payload = {
        "session_fingerprint": session_fingerprint,
        "selected_tenant_id": selected_tenant_id,
        "filters_by_module": filters_by_module,
        "pagination_by_module": pagination_by_module,
    }
    path = _context_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def restore_compatible_context(*, session_fingerprint: str) -> dict[str, Any]:
    payload = load_context()
    if not payload:
        return {}
    if payload.get("session_fingerprint") != session_fingerprint:
        clear_context()
        return {}
    return payload


def clear_context() -> None:
    path = _context_path()
    if path.exists():
        path.unlink()


def save_auth_recovery_context(
    *,
    reason: str,
    current_module: str,
    selected_tenant_id: str | None,
    filters_by_module: dict[str, dict[str, str]],
    pagination_by_module: dict[str, dict[str, int]],
) -> None:
    payload = {
        "reason": reason,
        "current_module": current_module,
        "selected_tenant_id": selected_tenant_id,
        "filters_by_module": filters_by_module,
        "pagination_by_module": pagination_by_module,
    }
    path = _recovery_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_auth_recovery_context() -> dict[str, Any]:
    path = _recovery_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (ValueError, OSError):
        return {}


def clear_auth_recovery_context() -> None:
    path = _recovery_path()
    if path.exists():
        path.unlink()
