from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MediaResolveRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku: str
    var1_value: str | None = None
    var2_value: str | None = None
    fallback_sku: bool = True


class MediaAsset(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_id: str | None = None
    url: str | None = None
    thumb_url: str | None = None
    source: str | None = None
    updated_at: datetime | None = None


class MediaMapping(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    asset_id: str | None = None
    source: str | None = None
    updated_at: datetime | None = None


class MediaResolveResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    request: MediaResolveRequest
    resolved: MediaAsset
    source: str = "PLACEHOLDER"
    trace_id: str | None = None
