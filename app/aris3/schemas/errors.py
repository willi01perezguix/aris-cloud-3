from pydantic import BaseModel


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None
    trace_id: str | None = None


class ApiValidationErrorItem(BaseModel):
    field: str | None = None
    message: str
    type: str
    loc: list[str | int] | None = None
    input: object | None = None
    ctx: dict | None = None


class ApiValidationErrorDetails(BaseModel):
    errors: list[ApiValidationErrorItem]


class ApiValidationErrorResponse(ApiErrorResponse):
    details: ApiValidationErrorDetails | dict | None = None
