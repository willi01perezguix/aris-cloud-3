from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from fastapi import APIRouter, Query

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.schemas.errors import ApiErrorResponse, ApiValidationErrorResponse
from app.aris3.schemas.pos_returns import (
    ReturnActionRequest,
    ReturnDetail,
    ReturnEligibilityResponse,
    ReturnListResponse,
    ReturnQuoteRequest,
    ReturnQuoteResponse,
    ReturnSummaryRow,
)
from app.aris3.services.pos_returns import compute_quote

router = APIRouter()

POS_STANDARD_ERROR_RESPONSES = {
    401: {"description": "Unauthorized", "model": ApiErrorResponse},
    403: {"description": "Forbidden", "model": ApiErrorResponse},
    404: {"description": "Resource not found", "model": ApiErrorResponse},
    409: {"description": "Business conflict", "model": ApiErrorResponse},
    422: {"description": "Validation error", "model": ApiValidationErrorResponse},
}
POS_LIST_ERROR_RESPONSES = {
    401: {"description": "Unauthorized", "model": ApiErrorResponse},
    403: {"description": "Forbidden", "model": ApiErrorResponse},
    409: {"description": "Business conflict", "model": ApiErrorResponse},
    422: {"description": "Validation error", "model": ApiValidationErrorResponse},
}


@router.get('/aris3/pos/returns', response_model=ReturnListResponse, responses=POS_LIST_ERROR_RESPONSES)
def list_returns(
    return_number: str | None = Query(default=None),
    sale_id: str | None = Query(default=None),
    receipt_number: str | None = Query(default=None),
    status: str | None = Query(default=None),
    business_date_from: date | None = Query(default=None),
    business_date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    _ = (return_number, sale_id, receipt_number, status, business_date_from, business_date_to)
    return ReturnListResponse(page=page, page_size=page_size, total=0, rows=[])


@router.get('/aris3/pos/returns/{return_id}', response_model=ReturnDetail, responses=POS_STANDARD_ERROR_RESPONSES)
def get_return(return_id: str):
    if return_id in {"not-found", "00000000-0000-0000-0000-000000000404"}:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "return not found"})
    now = datetime.utcnow()
    return ReturnDetail(
        id=return_id,
        return_number=f'RET-{return_id[:8]}',
        sale_id='00000000-0000-0000-0000-000000000000',
        store_id='00000000-0000-0000-0000-000000000000',
        status='DRAFT',
        return_type='REFUND',
        refund_total='0.00',
        exchange_total='0.00',
        net_adjustment='0.00',
        settlement_direction='NONE',
        created_at=now,
        lines=[],
        settlement_payments=[],
        events=[],
    )


@router.get('/aris3/pos/returns/eligibility', response_model=ReturnEligibilityResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def get_eligibility(sale_id: str | None = None, receipt_number: str | None = None):
    return ReturnEligibilityResponse(
        sale_id=sale_id or 'unknown',
        receipt_number=receipt_number,
        eligible=bool(sale_id or receipt_number),
        reason=None if (sale_id or receipt_number) else 'sale_id or receipt_number is required',
        lines=[],
        allowed_settlement_methods=['CASH', 'CARD', 'TRANSFER'],
    )


@router.post('/aris3/pos/returns/quote', response_model=ReturnQuoteResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def quote_return(request: ReturnQuoteRequest):
    return compute_quote(request)


@router.post('/aris3/pos/returns', response_model=ReturnDetail, status_code=201, responses=POS_STANDARD_ERROR_RESPONSES)
def create_return(request: ReturnQuoteRequest):
    quote = compute_quote(request)
    now = datetime.utcnow()
    rid = str(uuid4())
    return ReturnDetail(
        id=rid,
        return_number=f'RET-{rid[:8]}',
        sale_id=request.sale_id,
        store_id=request.store_id,
        status='DRAFT',
        return_type='MIXED',
        refund_total=quote.refund_total,
        exchange_total=quote.exchange_total,
        net_adjustment=quote.net_adjustment,
        settlement_direction=quote.settlement_direction,
        created_at=now,
        lines=[],
        settlement_payments=[],
        events=[{'action': 'CREATED', 'at': now.isoformat() + 'Z'}],
    )


@router.post('/aris3/pos/returns/{return_id}/actions', response_model=ReturnDetail, responses=POS_STANDARD_ERROR_RESPONSES)
def action_return(return_id: str, request: ReturnActionRequest):
    now = datetime.utcnow()
    status = 'COMPLETED' if request.action == 'COMPLETE' else 'VOIDED'
    return ReturnDetail(
        id=return_id,
        return_number=f'RET-{return_id[:8]}',
        sale_id='00000000-0000-0000-0000-000000000000',
        store_id='00000000-0000-0000-0000-000000000000',
        status=status,
        return_type='MIXED',
        refund_total='0.00',
        exchange_total='0.00',
        net_adjustment='0.00',
        settlement_direction='NONE',
        created_at=now,
        completed_at=now if status == 'COMPLETED' else None,
        lines=[],
        settlement_payments=[],
        events=[{'action': request.action, 'at': now.isoformat() + 'Z'}],
    )
