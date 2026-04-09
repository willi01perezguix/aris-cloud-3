from fastapi import FastAPI

from app.aris3.api import api_router
from app.aris3.core.logging import configure_logging
from app.aris3.middleware.observability import ObservabilityMiddleware
from app.aris3.middleware.trace import TraceIdMiddleware
from app.aris3.middleware.idempotency_guard import IdempotencyGuardMiddleware
from app.aris3.middleware.tenant import TenantContextMiddleware
from app.aris3.core.errors import setup_exception_handlers
from app.aris3.db.schema_guard import verify_schema_alignment
from app.aris3.openapi import harden_openapi_schema


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="ARIS-CLOUD-3")
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(IdempotencyGuardMiddleware)
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(ObservabilityMiddleware)
    setup_exception_handlers(app)
    app.include_router(api_router)
    app.openapi = lambda: harden_openapi_schema(app)

    @app.on_event("startup")
    def _verify_schema_alignment_on_startup() -> None:
        verify_schema_alignment()

    return app


app = create_app()
