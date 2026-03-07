from pydantic import BaseModel, ConfigDict


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None
    trace_id: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "NOT_FOUND",
                    "message": "sale not found",
                    "details": {"message": "sale_id does not exist", "sale_id": "00000000-0000-0000-0000-000000009999"},
                    "trace_id": "trace-sale-not-found-001",
                },
                {
                    "code": "VALIDATION_ERROR",
                    "message": "invalid action for current state",
                    "details": {"message": "sale must be DRAFT to cancel", "action": "CANCEL", "status": "PAID"},
                    "trace_id": "trace-invalid-action-002",
                },
                {
                    "code": "BUSINESS_CONFLICT",
                    "message": "returnable_qty exceeded",
                    "details": {"message": "requested qty exceeds returnable_qty", "sale_line_id": "line-123", "returnable_qty": 1, "requested_qty": 2},
                    "trace_id": "trace-return-qty-003",
                },
            ]
        }
    )


class ApiValidationErrorItem(BaseModel):
    field: str | None = None
    message: str
    type: str


class ApiValidationErrorDetails(BaseModel):
    errors: list[ApiValidationErrorItem]


class ApiValidationErrorResponse(ApiErrorResponse):
    details: ApiValidationErrorDetails | dict | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Validation error",
                "details": {
                    "errors": [
                        {
                            "field": "lines[0].sku",
                            "message": "sku is required for SKU lines",
                            "type": "value_error",
                        }
                    ]
                },
                "trace_id": "trace-validation-004",
            }
        }
    )
