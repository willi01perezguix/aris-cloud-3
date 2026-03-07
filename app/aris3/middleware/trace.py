import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        header_id = (
            request.headers.get("X-Trace-ID")
            or request.headers.get("X-Request-ID")
            or request.headers.get("Request-ID")
        )
        trace_id = header_id or f"trace-{uuid.uuid4()}"
        request.state.trace_id = trace_id
        response: Response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
