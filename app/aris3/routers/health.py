from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text

from app.aris3.core.errors import error_response
from app.aris3.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request, db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        trace_id = getattr(request.state, "trace_id", "")
        return error_response(
            code="db_unavailable",
            message="Database unavailable",
            details=str(exc),
            trace_id=trace_id,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return {"status": "ready"}
