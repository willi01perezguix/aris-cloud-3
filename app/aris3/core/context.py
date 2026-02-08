from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class RequestContext:
    user_id: str | None
    tenant_id: str | None
    store_id: str | None
    role: str | None
    trace_id: str


def build_request_context(
    *,
    user_id: str | None,
    tenant_id: str | None,
    store_id: str | None,
    role: str | None,
    trace_id: str,
) -> RequestContext:
    return RequestContext(
        user_id=user_id,
        tenant_id=tenant_id,
        store_id=store_id,
        role=role,
        trace_id=trace_id,
    )


def get_request_context(request: Request) -> RequestContext:
    context = getattr(request.state, "context", None)
    if isinstance(context, RequestContext):
        return context
    return build_request_context(
        user_id=getattr(request.state, "user_id", None),
        tenant_id=getattr(request.state, "tenant_id", None),
        store_id=getattr(request.state, "store_id", None),
        role=getattr(request.state, "role", None),
        trace_id=getattr(request.state, "trace_id", ""),
    )
