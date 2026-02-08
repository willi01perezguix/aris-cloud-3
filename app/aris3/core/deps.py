from fastapi import Depends, Request
from jose import JWTError
from pydantic import ValidationError

from app.aris3.core.context import RequestContext, build_request_context, get_request_context
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.security import TokenData, decode_token, oauth2_scheme
from app.aris3.db.session import get_db
from app.aris3.repos.users import UserRepository
from app.aris3.services.access_control import AccessControlService


def get_current_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        payload = decode_token(token)
        return TokenData(**payload)
    except (JWTError, ValidationError, TypeError) as exc:
        raise AppError(ErrorCatalog.INVALID_TOKEN) from exc


def get_current_user(token_data: TokenData = Depends(get_current_token_data), db=Depends(get_db)):
    user_id = token_data.sub
    if not user_id:
        raise AppError(ErrorCatalog.INVALID_TOKEN)

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise AppError(ErrorCatalog.INVALID_TOKEN)
    return user


def require_active_user(user=Depends(get_current_user)):
    if not user.is_active or user.status != "active":
        raise AppError(ErrorCatalog.USER_INACTIVE)
    return user


def require_request_context(
    request: Request,
    token_data: TokenData = Depends(get_current_token_data),
) -> RequestContext:
    trace_id = getattr(request.state, "trace_id", "")
    context = build_request_context(
        user_id=token_data.sub,
        tenant_id=token_data.tenant_id,
        store_id=token_data.store_id,
        role=token_data.role,
        trace_id=trace_id,
    )
    request.state.context = context
    return context


def require_permission(permission_key: str):
    def dependency(
        request: Request,
        token_data: TokenData = Depends(get_current_token_data),
        context: RequestContext = Depends(require_request_context),
        db=Depends(get_db),
    ):
        cache = getattr(request.state, "permission_cache", None)
        if cache is None:
            cache = {}
            request.state.permission_cache = cache
        service = AccessControlService(db, cache=cache)
        decision = service.evaluate_permission(permission_key, context, token_data)
        if not decision.allowed:
            raise AppError(ErrorCatalog.PERMISSION_DENIED)
        return decision

    return dependency


__all__ = [
    "get_current_token_data",
    "get_current_user",
    "require_active_user",
    "require_request_context",
    "get_request_context",
    "require_permission",
]
