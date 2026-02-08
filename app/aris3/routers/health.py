from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.core.errors import error_response
from app.aris3.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    trace_id = getattr(request.state, "trace_id", "")
    return {"status": "ok", "trace_id": trace_id}


@router.get("/ready")
async def ready(request: Request, db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        trace_id = getattr(request.state, "trace_id", "")
        return error_response(
            code=ErrorCatalog.DB_UNAVAILABLE.code,
            message=ErrorCatalog.DB_UNAVAILABLE.message,
            details=str(exc),
            trace_id=trace_id,
            status_code=ErrorCatalog.DB_UNAVAILABLE.status_code,
        )
    trace_id = getattr(request.state, "trace_id", "")
    return {"status": "ready", "trace_id": trace_id}
