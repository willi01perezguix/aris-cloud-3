import logging
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.metrics import metrics


logger = logging.getLogger(__name__)


_HTTP_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "INVALID_TOKEN",
    403: "PERMISSION_DENIED",
    404: "RESOURCE_NOT_FOUND",
    409: "CONFLICT",
}


def _set_error_context(request: Request, code: str, exc: Exception | None = None) -> None:
    request.state.error_code = code
    if exc is not None:
        request.state.error_class = exc.__class__.__name__


def _is_lock_timeout(exc: Exception) -> bool:
    if isinstance(exc, OperationalError):
        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "lock timeout",
                "deadlock detected",
                "database is locked",
                "could not obtain lock",
            )
        )
    return False


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


def _record_idempotency_failure(request: Request, status_code: int, response_body: dict) -> None:
    context = getattr(request.state, "idempotency", None)
    if context is None:
        return
    context.record_failure(status_code=status_code, response_body=response_body)


def _http_error_code(status_code: int) -> str:
    return _HTTP_STATUS_CODES.get(status_code, "HTTP_ERROR")



def _json_safe(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_json_safe(item) for item in value)
    return value


def _field_from_loc(loc: list) -> str | None:
    if not loc:
        return None
    if loc[0] in {"body", "query", "path", "header", "cookie"}:
        loc = loc[1:]
    if not loc:
        return None

    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))
    return ".".join(parts)


def _validation_error_details(exc: RequestValidationError) -> dict:
    errors = []
    for error in exc.errors():
        loc = list(error.get("loc", []))
        errors.append(
            {
                "field": _field_from_loc(loc),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "validation_error"),
            }
        )
    return {"errors": errors}


def _http_error_payload(request: Request, exc: HTTPException) -> dict:
    if exc.status_code == 401:
        code = ErrorCatalog.INVALID_TOKEN.code
        default_message = ErrorCatalog.INVALID_TOKEN.message
    elif exc.status_code == 403:
        code = ErrorCatalog.PERMISSION_DENIED.code
        default_message = ErrorCatalog.PERMISSION_DENIED.message
    elif exc.status_code == 404:
        code = ErrorCatalog.RESOURCE_NOT_FOUND.code
        default_message = ErrorCatalog.RESOURCE_NOT_FOUND.message
    elif exc.status_code == 409:
        code = "CONFLICT"
        default_message = "Resource conflict"
    else:
        code = _http_error_code(exc.status_code)
        default_message = "HTTP error"

    detail = exc.detail
    message = default_message
    details = None

    if detail is not None and exc.status_code != 401:
        message = str(detail)

    if isinstance(detail, dict):
        if {"code", "message"}.issubset(detail.keys()):
            payload = dict(detail)
            payload.setdefault("trace_id", _trace_id(request))
            payload.setdefault("details", None)
            return payload

        message = str(detail.get("message", default_message))
        if "details" in detail:
            details = detail.get("details")
        else:
            details = {key: value for key, value in detail.items() if key != "message"} or None
    elif isinstance(detail, list):
        details = {"errors": detail}

    if details is None and exc.status_code in {404, 409}:
        details = {
            "path": str(request.url.path),
            "method": request.method,
        }

    return {
        "code": code,
        "message": message,
        "details": details,
        "trace_id": _trace_id(request),
    }


def error_response(code: str, message: str, details: object, trace_id: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details,
            "trace_id": trace_id,
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        code = exc.error.code
        message = exc.error.message
        details = exc.details
        if exc.error.status_code == 401:
            code = ErrorCatalog.INVALID_TOKEN.code

        if exc.error.status_code == ErrorCatalog.VALIDATION_ERROR.status_code and code == ErrorCatalog.VALIDATION_ERROR.code:
            if not isinstance(details, dict) or "errors" not in details:
                details = {
                    "errors": [
                        {
                            "field": None,
                            "message": (details or {}).get("message", message) if isinstance(details, dict) else message,
                            "type": "validation_error",
                        }
                    ]
                }

        _set_error_context(request, code, exc)
        payload = {
            "code": code,
            "message": message,
            "details": details,
            "trace_id": _trace_id(request),
        }
        _record_idempotency_failure(request, exc.error.status_code, payload)
        headers = {}
        if exc.error.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(status_code=exc.error.status_code, content=payload, headers=headers)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        payload = _http_error_payload(request, exc)
        _set_error_context(request, payload["code"], exc)
        _record_idempotency_failure(request, exc.status_code, payload)
        headers = getattr(exc, "headers", None) or {}
        if exc.status_code == 401:
            headers = {**headers, "WWW-Authenticate": "Bearer"}
        return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        _set_error_context(request, ErrorCatalog.VALIDATION_ERROR.code, exc)
        payload = {
            "code": ErrorCatalog.VALIDATION_ERROR.code,
            "message": ErrorCatalog.VALIDATION_ERROR.message,
            "details": _validation_error_details(exc),
            "trace_id": _trace_id(request),
        }
        _record_idempotency_failure(request, ErrorCatalog.VALIDATION_ERROR.status_code, payload)
        return JSONResponse(status_code=ErrorCatalog.VALIDATION_ERROR.status_code, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if _is_lock_timeout(exc):
            _set_error_context(request, ErrorCatalog.LOCK_TIMEOUT.code, exc)
            metrics.increment_lock_wait_timeout()
            payload = {
                "code": ErrorCatalog.LOCK_TIMEOUT.code,
                "message": ErrorCatalog.LOCK_TIMEOUT.message,
                "details": {"type": exc.__class__.__name__},
                "trace_id": _trace_id(request),
            }
            _record_idempotency_failure(request, ErrorCatalog.LOCK_TIMEOUT.status_code, payload)
            return JSONResponse(status_code=ErrorCatalog.LOCK_TIMEOUT.status_code, content=payload)
        _set_error_context(request, ErrorCatalog.INTERNAL_ERROR.code, exc)
        logger.exception("Unhandled exception trace_id=%s", _trace_id(request), exc_info=exc)
        payload = {
            "code": ErrorCatalog.INTERNAL_ERROR.code,
            "message": ErrorCatalog.INTERNAL_ERROR.message,
            "details": {"type": exc.__class__.__name__},
            "trace_id": _trace_id(request),
        }
        _record_idempotency_failure(request, ErrorCatalog.INTERNAL_ERROR.status_code, payload)
        return JSONResponse(status_code=ErrorCatalog.INTERNAL_ERROR.status_code, content=payload)
