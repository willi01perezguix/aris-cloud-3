from fastapi import FastAPI

from app.aris3.api import api_router
from app.aris3.middleware.trace import TraceIdMiddleware
from app.aris3.middleware.tenant import TenantContextMiddleware
from app.aris3.core.errors import setup_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="ARIS-CLOUD-3")
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(TenantContextMiddleware)
    setup_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
