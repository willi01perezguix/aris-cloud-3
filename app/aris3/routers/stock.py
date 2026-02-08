from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.aris3.core.deps import get_current_token_data, require_active_user
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import is_superadmin
from app.aris3.db.session import get_db
from app.aris3.repos.stock import StockQueryFilters, StockRepository
from app.aris3.schemas.stock import StockQueryMeta, StockQueryResponse, StockQueryTotals, StockRow


router = APIRouter()


def _resolve_tenant_id(token_data, tenant_id: str | None) -> str:
    if is_superadmin(token_data.role):
        if not tenant_id:
            raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)
        return tenant_id
    if not token_data.tenant_id:
        raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)
    if tenant_id and tenant_id != token_data.tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    return token_data.tenant_id


@router.get("/aris3/stock", response_model=StockQueryResponse)
def list_stock(
    request: Request,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    db=Depends(get_db),
    q: str | None = None,
    description: str | None = None,
    var1_value: str | None = None,
    var2_value: str | None = None,
    sku: str | None = None,
    epc: str | None = None,
    location_code: str | None = None,
    pool: str | None = None,
    tenant_id: str | None = None,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    repo = StockRepository(db)
    filters = StockQueryFilters(
        tenant_id=scoped_tenant_id,
        q=q,
        description=description,
        var1_value=var1_value,
        var2_value=var2_value,
        sku=sku,
        epc=epc,
        location_code=location_code,
        pool=pool,
        from_date=from_date,
        to_date=to_date,
    )
    rows, totals, resolved_sort_by = repo.list_stock(
        filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    response_rows = [
        StockRow(
            id=str(row.id),
            tenant_id=str(row.tenant_id),
            sku=row.sku,
            description=row.description,
            var1_value=row.var1_value,
            var2_value=row.var2_value,
            epc=row.epc,
            location_code=row.location_code,
            pool=row.pool,
            status=row.status,
            location_is_vendible=row.location_is_vendible,
            image_asset_id=str(row.image_asset_id) if row.image_asset_id else None,
            image_url=row.image_url,
            image_thumb_url=row.image_thumb_url,
            image_source=row.image_source,
            image_updated_at=row.image_updated_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    meta = StockQueryMeta(
        page=page,
        page_size=page_size,
        sort_by=resolved_sort_by,
        sort_dir=sort_dir,
    )
    return StockQueryResponse(
        meta=meta,
        rows=response_rows,
        totals=StockQueryTotals(**totals),
    )
