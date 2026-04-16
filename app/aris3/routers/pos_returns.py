from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.session import get_db
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
from app.aris3.services.pos_returns import PosReturnsService

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

RETURN_ERROR_EXAMPLES = {
    "401": {"code": "UNAUTHORIZED", "message": "Authentication required", "details": {"message": "Bearer token is missing or expired"}, "trace_id": "trace-returns-401"},
    "403": {"code": "FORBIDDEN", "message": "You do not have access to this store", "details": {"required_permission": "POS_RETURN_VIEW"}, "trace_id": "trace-returns-403"},
    "404": {"code": "NOT_FOUND", "message": "return not found", "details": {"return_id": "00000000-0000-0000-0000-000000009999"}, "trace_id": "trace-returns-404"},
    "409": {"code": "BUSINESS_CONFLICT", "message": "return exceeds returnable_qty", "details": {"sale_line_id": "line-001", "returnable_qty": 1, "requested_qty": 2}, "trace_id": "trace-returns-409"},
}


@router.get('/aris3/pos/returns', response_model=ReturnListResponse, responses=POS_LIST_ERROR_RESPONSES, openapi_extra={
    "responses": {
        "401": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["401"]}}},
        "403": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["403"]}}},
        "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "business_date_from", "message": "business_date_from must be <= business_date_to", "type": "value_error"}]}, "trace_id": "trace-returns-list-422"}}}},
    }
})
def list_returns(
    return_number: str | None = Query(default=None),
    sale_id: str | None = Query(default=None),
    receipt_number: str | None = Query(default=None),
    status: str | None = Query(default=None),
    business_date_from: date | None = Query(default=None),
    business_date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db=Depends(get_db),
):
    _ = (return_number, status, business_date_from, business_date_to)
    service = PosReturnsService(db)
    return service.list_returns(sale_id=sale_id, receipt_number=receipt_number, page=page, page_size=page_size)


@router.get('/aris3/pos/returns/{return_id}', response_model=ReturnDetail, responses={k: v for k, v in POS_STANDARD_ERROR_RESPONSES.items() if k != 409}, openapi_extra={
    "responses": {
        "401": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["401"]}}},
        "403": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["403"]}}},
        "404": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["404"]}}},
    }
})
def get_return(return_id: str, db=Depends(get_db)):
    service = PosReturnsService(db)
    return service.get_return(return_id)


@router.get('/aris3/pos/returns/eligibility', response_model=ReturnEligibilityResponse, responses=POS_STANDARD_ERROR_RESPONSES, openapi_extra={
    "responses": {
        "401": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["401"]}}},
        "403": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["403"]}}},
        "404": {"content": {"application/json": {"example": {"code": "NOT_FOUND", "message": "sale not found", "details": {"sale_id": "00000000-0000-0000-0000-000000009999"}, "trace_id": "trace-returns-eligibility-404"}}}},
        "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "sale_id", "message": "sale_id or receipt_number is required", "type": "value_error"}]}, "trace_id": "trace-returns-eligibility-422"}}}},
    }
})
def get_eligibility(sale_id: str | None = None, receipt_number: str | None = None, db=Depends(get_db)):
    service = PosReturnsService(db)
    return service.get_eligibility(sale_id=sale_id, receipt_number=receipt_number)


@router.post(
    '/aris3/pos/returns/quote',
    response_model=ReturnQuoteResponse,
    responses=POS_STANDARD_ERROR_RESPONSES,
    summary='Quote return draft',
    description='Previews refund/exchange totals using canonical line selectors (`line_type` + `sku`/`epc`) for exchange lines.',
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "canonical": {
                            "value": {
                                "transaction_id": "txn-return-quote-1001",
                                "store_id": "00000000-0000-0000-0000-000000000001",
                                "sale_id": "00000000-0000-0000-0000-000000000111",
                                "items": [{"sale_line_id": "line-1", "qty": 1, "condition": "NEW", "resolution": "EXCHANGE"}],
                                "exchange_lines": [{"line_type": "SKU", "sku": "SKU-888", "qty": 1}],
                            }
                        }
                    }
                }
            }
        },
        "responses": {
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "exchange_lines[0].epc", "message": "epc is required for EPC lines", "type": "value_error"}]}, "trace_id": "trace-returns-quote-422"}}}},
        },
    },
)
def quote_return(request: ReturnQuoteRequest, db=Depends(get_db)):
    service = PosReturnsService(db)
    return service.compute_quote(request)


@router.post(
    '/aris3/pos/returns',
    response_model=ReturnDetail,
    status_code=201,
    responses=POS_STANDARD_ERROR_RESPONSES,
    summary='Create draft return',
    description='Creates a return in DRAFT status. Completion is done later via return actions.',
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "canonical": {
                            "value": {
                                "transaction_id": "txn-return-create-1001",
                                "store_id": "00000000-0000-0000-0000-000000000001",
                                "sale_id": "00000000-0000-0000-0000-000000000111",
                                "items": [{"sale_line_id": "line-1", "qty": 1, "condition": "NEW", "resolution": "REFUND"}],
                                "exchange_lines": [{"line_type": "SKU", "sku": "SKU-123", "qty": 1}],
                            }
                        }
                    }
                }
            }
        },
        "responses": {
            "201": {"content": {"application/json": {"example": {"id": "00000000-0000-0000-0000-000000000778", "return_number": "RET-00000078", "sale_id": "00000000-0000-0000-0000-000000000111", "store_id": "00000000-0000-0000-0000-000000000001", "status": "DRAFT", "return_type": "MIXED", "refund_total": "25.00", "exchange_total": "0.00", "net_adjustment": "-25.00", "settlement_direction": "STORE_REFUNDS", "created_at": "2026-01-15T12:10:00Z", "completed_at": None, "lines": [], "settlement_payments": [], "exchange_sale_summary": None, "events": [{"action": "CREATED", "at": "2026-01-15T12:10:00Z", "by_user_id": "00000000-0000-0000-0000-000000000020"}]}}}},
            "401": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["401"]}}},
            "403": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["403"]}}},
            "404": {"content": {"application/json": {"example": RETURN_ERROR_EXAMPLES["404"]}}},
            "409": {"content": {"application/json": {"example": {"code": "BUSINESS_CONFLICT", "message": "return exceeds returnable_qty", "details": {"sale_line_id": "line-001", "returnable_qty": 1, "requested_qty": 2}, "trace_id": "trace-returns-409"}}}},
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "items", "message": "items must not be empty", "type": "value_error"}]}, "trace_id": "trace-returns-create-422"}}}},
        },
    },
)
def create_return(request: ReturnQuoteRequest, db=Depends(get_db)):
    service = PosReturnsService(db)
    return service.create_draft(request)


@router.post(
    '/aris3/pos/returns/{return_id}/actions',
    response_model=ReturnDetail,
    responses=POS_STANDARD_ERROR_RESPONSES,
    summary='Execute return action',
    description='Action request is discriminated by `action` with action-specific required fields.',
    openapi_extra={
        "responses": {
            "200": {"content": {"application/json": {"example": {"id": "00000000-0000-0000-0000-000000000779", "return_number": "RET-00000079", "sale_id": "00000000-0000-0000-0000-000000000111", "store_id": "00000000-0000-0000-0000-000000000001", "status": "COMPLETED", "return_type": "MIXED", "refund_total": "25.00", "exchange_total": "0.00", "net_adjustment": "-25.00", "settlement_direction": "STORE_REFUNDS", "created_at": "2026-01-15T12:10:00Z", "completed_at": "2026-01-15T12:15:00Z", "lines": [], "settlement_payments": [{"method": "CASH", "amount": "25.00", "authorization_code": None, "bank_name": None, "voucher_number": None}], "exchange_sale_summary": None, "events": [{"action": "CREATED", "at": "2026-01-15T12:10:00Z", "by_user_id": "00000000-0000-0000-0000-000000000020"}, {"action": "COMPLETE", "at": "2026-01-15T12:15:00Z", "by_user_id": "00000000-0000-0000-0000-000000000020"}]}}}},
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "settlement_payments", "message": "settlement_payments are required for COMPLETE when net adjustment requires settlement", "type": "value_error"}]}, "trace_id": "trace-returns-action-422"}}}},
        },
    },
)
def action_return(return_id: str, request: ReturnActionRequest, db=Depends(get_db)):
    service = PosReturnsService(db)
    return service.apply_action(return_id, request)
