from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.aris3.core.db_timing import get_db_time_ms, start_db_timer, stop_db_timer
from app.aris3.core.logging import log_json
from app.aris3.core.metrics import metrics

logger = logging.getLogger("aris3.request")


def build_request_log_payload(
    *,
    request: Request,
    response: Response | None,
    latency_ms: float,
    db_time_ms: float | None,
) -> dict:
    route = None
    scope_route = request.scope.get("route")
    if scope_route is not None:
        route = getattr(scope_route, "path", None)
    route = route or request.url.path
    status_code = getattr(response, "status_code", 500)
    payload = {
        "event": "http_request",
        "trace_id": getattr(request.state, "trace_id", ""),
        "tenant_id": getattr(request.state, "tenant_id", None),
        "user_id": getattr(request.state, "user_id", None),
        "route": route,
        "method": request.method,
        "status_code": status_code,
        "latency_ms": round(latency_ms, 2),
        "db_time_ms": round(db_time_ms, 2) if db_time_ms is not None else None,
        "error_code": getattr(request.state, "error_code", None),
        "error_class": getattr(request.state, "error_class", None),
    }
    return payload


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        token = start_db_timer()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000
            db_time_ms = get_db_time_ms()
            stop_db_timer(token)
            payload = build_request_log_payload(
                request=request,
                response=response,
                latency_ms=latency_ms,
                db_time_ms=db_time_ms,
            )
            log_json(logger, payload)
            metrics.record_http_request(
                route=payload["route"],
                method=payload["method"],
                status_code=payload["status_code"],
                latency_ms=latency_ms,
            )
