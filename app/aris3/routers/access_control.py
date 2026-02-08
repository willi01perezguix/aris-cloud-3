from fastapi import APIRouter, Depends, Request

from app.aris3.core.deps import get_current_token_data, require_active_user, require_request_context
from app.aris3.db.session import get_db
from app.aris3.schemas.access_control import EffectivePermissionsResponse, PermissionEntry
from app.aris3.services.access_control import AccessControlService

router = APIRouter()


@router.get("/effective-permissions", response_model=EffectivePermissionsResponse)
async def effective_permissions(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    context=Depends(require_request_context),
    db=Depends(get_db),
):
    cache = getattr(request.state, "permission_cache", None)
    if cache is None:
        cache = {}
        request.state.permission_cache = cache
    service = AccessControlService(db, cache=cache)
    decisions = service.build_effective_permissions(context, token_data)
    return EffectivePermissionsResponse(
        user_id=context.user_id or token_data.sub,
        tenant_id=context.tenant_id or token_data.tenant_id,
        store_id=context.store_id or token_data.store_id,
        role=(context.role or token_data.role),
        permissions=[PermissionEntry(key=d.key, allowed=d.allowed, source=d.source) for d in decisions],
        trace_id=getattr(request.state, "trace_id", ""),
    )
