from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.aris3.core.config import settings
from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.core.errors import error_response
from app.aris3.db.session import get_db
from app.aris3.schemas.errors import ApiErrorResponse
from app.aris3.schemas.health import ServiceHealthResponse

router = APIRouter()


def _health_payload(request: Request, readiness: str) -> ServiceHealthResponse:
    return ServiceHealthResponse(
        ok=True,
        service="aris3",
        timestamp=datetime.now(timezone.utc),
        version=settings.APP_VERSION,
        trace_id=getattr(request.state, "trace_id", ""),
        readiness=readiness,
    )


@router.get("/health", response_model=ServiceHealthResponse, summary="Liveness probe")
async def health(request: Request):
    return _health_payload(request, readiness="live")


@router.get(
    "/ready",
    response_model=ServiceHealthResponse,
    summary="Readiness probe",
    responses={
        503: {
            "description": "Dependency unavailable (database readiness check failed).",
            "model": ApiErrorResponse,
        }
    },
)
async def ready(request: Request, db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        trace_id = getattr(request.state, "trace_id", "")
        request.state.error_code = ErrorCatalog.DB_UNAVAILABLE.code
        request.state.error_class = exc.__class__.__name__
        return error_response(
            code=ErrorCatalog.DB_UNAVAILABLE.code,
            message=ErrorCatalog.DB_UNAVAILABLE.message,
            details={"type": exc.__class__.__name__},
            trace_id=trace_id,
            status_code=ErrorCatalog.DB_UNAVAILABLE.status_code,
        )
    return _health_payload(request, readiness="ready")
