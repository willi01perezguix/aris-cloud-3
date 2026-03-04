from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema, field_serializer


Money = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value.quantize(Decimal('0.01')), 'f'), return_type=str, when_used='json'),
    WithJsonSchema({'type': 'string', 'pattern': r'^-?(0|[1-9]\d*)\.\d{2}$', 'example': '25.00'}),
]


class PosBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer('*', when_used='json')
    def serialize_decimals(self, value):
        if isinstance(value, Decimal):
            return format(value.quantize(Decimal('0.01')), 'f')
        return value


class ErrorResponse(PosBaseModel):
    code: str
    message: str
    details: dict | None = None
    trace_id: str | None = None


class ValidationErrorResponse(ErrorResponse):
    code: str = 'VALIDATION_ERROR'


class PaginatedResponse(PosBaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
