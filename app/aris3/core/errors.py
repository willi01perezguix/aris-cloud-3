from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.aris3.core.error_catalog import AppError, ErrorCatalog


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


def _record_idempotency_failure(request: Request, status_code: int, response_body: dict) -> None:
    context = getattr(request.state, "idempotency", None)
    if context is None:
        return
    context.record_failure(status_code=status_code, response_body=response_body)


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
        payload = {
            "code": exc.error.code,
            "message": exc.error.message,
            "details": exc.details,
            "trace_id": _trace_id(request),
        }
        _record_idempotency_failure(request, exc.error.status_code, payload)
        return JSONResponse(status_code=exc.error.status_code, content=payload)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == ErrorCatalog.INVALID_TOKEN.status_code:
            payload = {
                "code": ErrorCatalog.INVALID_TOKEN.code,
                "message": ErrorCatalog.INVALID_TOKEN.message,
                "details": exc.detail,
                "trace_id": _trace_id(request),
            }
            _record_idempotency_failure(request, exc.status_code, payload)
            return JSONResponse(status_code=exc.status_code, content=payload)
        payload = {
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "details": None,
            "trace_id": _trace_id(request),
        }
        _record_idempotency_failure(request, exc.status_code, payload)
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        payload = {
            "code": ErrorCatalog.VALIDATION_ERROR.code,
            "message": ErrorCatalog.VALIDATION_ERROR.message,
            "details": exc.errors(),
            "trace_id": _trace_id(request),
        }
        _record_idempotency_failure(request, ErrorCatalog.VALIDATION_ERROR.status_code, payload)
        return JSONResponse(status_code=ErrorCatalog.VALIDATION_ERROR.status_code, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        payload = {
            "code": ErrorCatalog.INTERNAL_ERROR.code,
            "message": ErrorCatalog.INTERNAL_ERROR.message,
            "details": str(exc),
            "trace_id": _trace_id(request),
        }
        _record_idempotency_failure(request, ErrorCatalog.INTERNAL_ERROR.status_code, payload)
        return JSONResponse(status_code=ErrorCatalog.INTERNAL_ERROR.status_code, content=payload)
