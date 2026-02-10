from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..exceptions import ApiError
from ..image_utils import ImageMemoCache, choose_best_image, placeholder_image_ref
from ..models_media import MediaAsset, MediaResolveRequest, MediaResolveResponse
from ..models_stock import StockQuery
from .base import BaseClient
from .stock_client import StockClient


@dataclass
class MediaClient(BaseClient):
    cache_ttl_seconds: int = 300

    def __post_init__(self) -> None:
        self._cache = ImageMemoCache(ttl_seconds=self.cache_ttl_seconds)

    def resolve_media(
        self,
        *,
        sku: str,
        var1_value: str | None = None,
        var2_value: str | None = None,
        fallback_sku: bool = True,
    ) -> MediaResolveResponse:
        return self.resolve_for_variant(sku, var1_value, var2_value, fallback_sku=fallback_sku)

    def resolve_for_variant(
        self,
        sku: str,
        var1_value: str | None,
        var2_value: str | None,
        *,
        fallback_sku: bool = True,
    ) -> MediaResolveResponse:
        request = MediaResolveRequest(sku=sku, var1_value=var1_value, var2_value=var2_value, fallback_sku=fallback_sku)
        cache_key = f"{sku}|{var1_value or ''}|{var2_value or ''}|{fallback_sku}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, MediaResolveResponse):
            return cached

        trace_id: str | None = None
        try:
            variant_row = self._resolve_stock_row(sku=sku, var1_value=var1_value, var2_value=var2_value)
            if variant_row is not None:
                response = self._response_from_row(request, variant_row, source="VARIANT")
                self._cache.set(cache_key, response)
                return response
            if fallback_sku:
                sku_row = self._resolve_stock_row(sku=sku, var1_value=None, var2_value=None)
                if sku_row is not None:
                    response = self._response_from_row(request, sku_row, source="SKU")
                    self._cache.set(cache_key, response)
                    return response
        except ApiError as exc:
            trace_id = exc.trace_id
            if exc.status_code in {401, 403, 404, 422}:
                raise
            raise

        response = MediaResolveResponse(
            request=request,
            resolved=MediaAsset(url=placeholder_image_ref(), thumb_url=placeholder_image_ref(), source="PLACEHOLDER"),
            source="PLACEHOLDER",
            trace_id=trace_id,
        )
        self._cache.set(cache_key, response)
        return response

    def get_mappings(self, **filters: Any) -> list[dict[str, Any]]:
        payload = self._request("GET", "/aris3/media/mappings", params=filters)
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        return []

    def list_assets(self, **filters: Any) -> list[dict[str, Any]]:
        payload = self._request("GET", "/aris3/media/assets", params=filters)
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        return []

    def _resolve_stock_row(self, *, sku: str, var1_value: str | None, var2_value: str | None) -> dict[str, Any] | None:
        client = StockClient(http=self.http, access_token=self.access_token)
        query = StockQuery(sku=sku, var1_value=var1_value, var2_value=var2_value, page=1, page_size=1)
        response = client.get_stock(query)
        for row in response.rows:
            payload = row.model_dump(mode="json")
            if not payload.get("image_url") and not payload.get("image_thumb_url"):
                continue
            return payload
        return None

    def _response_from_row(self, request: MediaResolveRequest, row: dict[str, Any], *, source: str) -> MediaResolveResponse:
        updated_at = row.get("image_updated_at")
        parsed_updated_at: datetime | None = None
        if isinstance(updated_at, str):
            try:
                parsed_updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except ValueError:
                parsed_updated_at = None
        elif isinstance(updated_at, datetime):
            parsed_updated_at = updated_at

        asset = MediaAsset(
            asset_id=row.get("image_asset_id"),
            url=row.get("image_url"),
            thumb_url=row.get("image_thumb_url") or row.get("image_url"),
            source=row.get("image_source") or source,
            updated_at=parsed_updated_at,
        )
        best_url = choose_best_image(asset, prefer_thumb=False)
        if not best_url:
            asset.url = placeholder_image_ref()
            asset.thumb_url = placeholder_image_ref()
            asset.source = "PLACEHOLDER"
            source = "PLACEHOLDER"
        return MediaResolveResponse(request=request, resolved=asset, source=source)
