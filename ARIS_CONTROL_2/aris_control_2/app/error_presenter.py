from __future__ import annotations

from typing import Any

from clients.aris3_client_sdk.errors import ApiError


def build_error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, ApiError):
        category = _classify_api_error(error)
        return {
            "category": category,
            "code": error.code,
            "message": error.message,
            "trace_id": error.trace_id,
            "action": _suggest_action(category),
        }
    return {
        "category": "internal",
        "code": "INTERNAL_ERROR",
        "message": str(error),
        "trace_id": None,
        "action": "Contactar soporte",
    }


def print_error_banner(payload: dict[str, Any]) -> None:
    print(
        "[ERROR] "
        f"category={payload.get('category')} "
        f"code={payload.get('code')} "
        f"message={payload.get('message')} "
        f"trace_id={payload.get('trace_id')} "
        f"acción={payload.get('action')}"
    )


def _classify_api_error(error: ApiError) -> str:
    if error.code == "NETWORK_ERROR":
        return "red/timeout"
    if error.status_code == 403:
        return "403"
    if error.status_code == 409:
        return "409"
    if error.status_code == 422:
        return "422"
    if error.status_code and error.status_code >= 500:
        return "500"
    return "api"


def _suggest_action(category: str) -> str:
    if category in {"red/timeout", "500", "409"}:
        return "Reintentar"
    return "Contactar soporte"
