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
            "status_code": error.status_code,
            "action": _suggest_action(category),
        }
    return {
        "category": "internal",
        "code": "INTERNAL_ERROR",
        "message": str(error),
        "trace_id": None,
        "status_code": None,
        "action": "Contactar soporte",
    }


def print_error_banner(payload: dict[str, Any]) -> None:
    trace_id = payload.get("trace_id") or "n/a"
    print(
        "[ERROR] "
        f"code={payload.get('code')} "
        f"message={payload.get('message')} "
        f"trace_id={trace_id} "
        f"category={payload.get('category')} "
        f"acción={payload.get('action')}"
    )


def _classify_api_error(error: ApiError) -> str:
    if error.code == "NETWORK_ERROR":
        return "red/timeout"
    if error.status_code == 403:
        return "403"
    if error.status_code == 401:
        return "401"
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
    if category == "401":
        return "Ir a login"
    if category == "403":
        return "Volver al inicio"
    return "Contactar soporte"
