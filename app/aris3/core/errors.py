from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


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
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return error_response(
            code="http_error",
            message=str(exc.detail),
            details=None,
            trace_id=_trace_id(request),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return error_response(
            code="validation_error",
            message="Validation error",
            details=exc.errors(),
            trace_id=_trace_id(request),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return error_response(
            code="internal_error",
            message="Internal server error",
            details=str(exc),
            trace_id=_trace_id(request),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
