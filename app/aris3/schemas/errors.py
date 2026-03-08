from pydantic import BaseModel, ConfigDict


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None
    trace_id: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "RESOURCE_CONFLICT",
                "message": "Operation could not be completed",
                "details": {"reason": "business rule violation"},
                "trace_id": "trace-generic-001",
            }
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
                            "field": "field_name",
                            "message": "Invalid value",
                            "type": "value_error",
                        }
                    ]
                },
                "trace_id": "trace-validation-001",
            }
        }
    )
