from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.aris3.services.idempotency import IDEMPOTENCY_HEADER, LEGACY_IDEMPOTENCY_HEADER


class IdempotencyGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        guarded_paths = ("/aris3/admin/", "/aris3/access-control/")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith(guarded_paths):
            key = request.headers.get(IDEMPOTENCY_HEADER) or request.headers.get(LEGACY_IDEMPOTENCY_HEADER)
            if not key:
                trace_id = getattr(request.state, "trace_id", "")
                payload = {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation error",
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
                return JSONResponse(status_code=422, content=payload)
        return await call_next(request)
