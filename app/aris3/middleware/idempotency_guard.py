from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.aris3.services.idempotency import IDEMPOTENCY_HEADER, LEGACY_IDEMPOTENCY_HEADER


class IdempotencyGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/aris3/admin/"):
            key = request.headers.get(IDEMPOTENCY_HEADER) or request.headers.get(LEGACY_IDEMPOTENCY_HEADER)
            if not key:
                trace_id = getattr(request.state, "trace_id", "")
                payload = {
                    "code": "IDEMPOTENCY_KEY_REQUIRED",
                    "message": "Idempotency key required",
                    "details": {
                        "errors": [
                            {
                                "field": IDEMPOTENCY_HEADER,
                                "message": "Idempotency-Key header is required",
                                "type": "missing",
                            }
                        ]
                    },
                    "trace_id": trace_id,
                }
                return JSONResponse(status_code=400, content=payload)
        return await call_next(request)
