from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..exceptions import ForbiddenError, ValidationError
from ..models_reports import (
    ReportCalendarResponse,
    ReportDailyResponse,
    ReportFilter,
    ReportOverviewResponse,
    ReportProfitSummaryResponse,
)
from .base import BaseClient


@dataclass
class ReportsClient(BaseClient):
    def get_sales_overview(self, filters: ReportFilter | Mapping[str, Any] | None = None) -> ReportOverviewResponse:
        return self._fetch_report("/aris3/reports/overview", ReportOverviewResponse, filters)

    def get_sales_daily(self, filters: ReportFilter | Mapping[str, Any] | None = None) -> ReportDailyResponse:
        return self._fetch_report("/aris3/reports/daily", ReportDailyResponse, filters)

    def get_sales_calendar(self, filters: ReportFilter | Mapping[str, Any] | None = None) -> ReportCalendarResponse:
        return self._fetch_report("/aris3/reports/calendar", ReportCalendarResponse, filters)

    def get_profit_summary(self, filters: ReportFilter | Mapping[str, Any] | None = None) -> ReportProfitSummaryResponse:
        # Current contract does not expose a dedicated profit summary route.
        overview = self.get_sales_overview(filters)
        return ReportProfitSummaryResponse(meta=overview.meta, totals=overview.totals)

    def _fetch_report(self, path: str, model_type: type[Any], filters: ReportFilter | Mapping[str, Any] | None) -> Any:
        query = None
        if filters is not None:
            payload = _coerce_model(filters, ReportFilter)
            query = payload.model_dump(by_alias=True, exclude_none=True, mode="json")
        try:
            data = self._request("GET", path, params=query)
        except ValidationError as exc:
            if exc.code == "VALIDATION_ERROR":
                raise ValidationError(
                    code="REPORT_INVALID_DATE_RANGE",
                    message=exc.message,
                    details=exc.details,
                    trace_id=exc.trace_id,
                    status_code=exc.status_code,
                ) from exc
            raise
        except ForbiddenError as exc:
            if exc.code in {"PERMISSION_DENIED", "STORE_SCOPE_MISMATCH", "CROSS_TENANT_ACCESS_DENIED"}:
                raise ForbiddenError(
                    code="REPORT_SCOPE_FORBIDDEN",
                    message=exc.message,
                    details=exc.details,
                    trace_id=exc.trace_id,
                    status_code=exc.status_code,
                ) from exc
            raise
        if not isinstance(data, dict):
            raise ValueError("Expected report response to be a JSON object")
        return model_type.model_validate(data)


def _coerce_model(value: Any, model_type: type[Any]):
    if isinstance(value, model_type):
        return value
    return model_type.model_validate(value)
