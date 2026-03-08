from datetime import datetime

from pydantic import BaseModel, Field


class ServiceHealthResponse(BaseModel):
    ok: bool = True
    service: str = Field(..., examples=["aris3"])
    timestamp: datetime
    version: str
    trace_id: str
    readiness: str | None = Field(default=None, examples=["live", "ready"])
