import json
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        header_id = (
            request.headers.get("X-Trace-Id")
            or request.headers.get("X-Trace-ID")
            or request.headers.get("X-Request-ID")
            or request.headers.get("Request-ID")
        )
        trace_id = header_id or f"trace-{uuid.uuid4()}"
        request.state.trace_id = trace_id
        response: Response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Trace-ID"] = trace_id

        content_type = (response.headers.get("content-type") or "").lower()
        if "application/json" in content_type and hasattr(response, "body"):
            try:
                payload = json.loads(response.body)
            except Exception:
                payload = None
            if isinstance(payload, dict) and "trace_id" not in payload:
                payload["trace_id"] = trace_id
                response.body = json.dumps(payload).encode("utf-8")
                response.headers["content-length"] = str(len(response.body))

        return response
