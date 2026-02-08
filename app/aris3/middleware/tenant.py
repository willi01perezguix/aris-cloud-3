from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.aris3.core.security import decode_token


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.tenant_id = None
        request.state.user_id = None
        request.state.role = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                payload = decode_token(token)
                request.state.tenant_id = payload.get("tenant_id")
                request.state.user_id = payload.get("sub")
                request.state.role = payload.get("role")
            except Exception:
                pass

        return await call_next(request)
