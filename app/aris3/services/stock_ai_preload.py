from __future__ import annotations

import base64
import csv
import io
import json
import logging
import re
import time
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any
from xml.etree import ElementTree

import httpx
from openpyxl import load_workbook

from app.aris3.core.config import settings
from app.aris3.core.error_catalog import AppError, ErrorCatalog


SUPPORTED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "text/csv",
    "text/tab-separated-values",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

EPC_KEYS = {"epc", "rfid", "tag"}
SALE_KEYS = {"venta", "sale", "sale_price", "precio venta"}
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
_MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
logger = logging.getLogger(__name__)


@dataclass
class UploadedSource:
    filename: str
    content_type: str
    content: bytes


class OpenAIInventoryClient:
    def __init__(self) -> None:
        self._api_key = settings.OPENAI_API_KEY
        configured_model = (settings.OPENAI_INVENTORY_MODEL or "").strip()
        if configured_model and _MODEL_NAME_PATTERN.match(configured_model):
            self._model = configured_model
        else:
            self._model = DEFAULT_OPENAI_MODEL
        logger.info(
            "stock.ai_preload.config api_key_present=%s model_configured=%s model_used=%s",
            bool(self._api_key),
            bool(configured_model),
            self._model,
        )

    def extract(
        self,
        *,
        prompt: str,
        attachments: list[UploadedSource],
        trace_id: str | None,
        tenant_id: str,
        store_id: str,
        document_type: str | None,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "OPENAI_API_KEY is not configured", "retryable": False, "model": self._model},
            )
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for item in attachments:
            encoded = base64.b64encode(item.content).decode("ascii")
            if item.content_type.startswith("image/"):
                content.append({"type": "input_image", "image_url": f"data:{item.content_type};base64,{encoded}"})
            else:
                content.append({"type": "input_file", "filename": item.filename, "file_data": f"data:{item.content_type};base64,{encoded}"})

        payload = {
            "model": self._model,
            "input": [{"role": "system", "content": [{"type": "input_text", "text": "Extract inventory lines."}]}, {"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "inventory_preload_extraction",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "document_summary": {"type": "object"},
                            "pricing_context": {"type": "object"},
                            "lines": {"type": "array"},
                            "warnings": {"type": "array"},
                        },
                        "required": ["document_summary", "pricing_context", "lines", "warnings"],
                        "additionalProperties": True,
                    },
                }
            },
        }

        timeout = httpx.Timeout(22.0, connect=3.0)
        start = time.perf_counter()
        logger.info(
            "stock.ai_preload.openai_call_started trace_id=%s tenant_id=%s store_id=%s document_type=%s text_only=%s files_count=%s model_used=%s",
            trace_id,
            tenant_id,
            store_id,
            document_type,
            len(attachments) == 0,
            len(attachments),
            self._model,
        )
        try:
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "stock.ai_preload.openai_call_finished trace_id=%s tenant_id=%s store_id=%s success=false timeout=true elapsed_ms=%s error_class=%s model_used=%s",
                trace_id,
                tenant_id,
                store_id,
                elapsed_ms,
                exc.__class__.__name__,
                self._model,
            )
            raise AppError(
                ErrorCatalog.AI_SERVICE_TIMEOUT,
                details={"message": "AI inventory analysis timed out", "retryable": True, "model": self._model},
            ) from exc
        except httpx.HTTPStatusError as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            status_code = exc.response.status_code if exc.response is not None else None
            body_text = (exc.response.text or "")[:500] if exc.response is not None else ""
            error_lower = body_text.lower()
            if status_code in (401, 403):
                error = ErrorCatalog.AI_AUTH_FAILED
                details = {"message": "OpenAI API key is invalid or unauthorized", "retryable": False, "model": self._model}
            elif status_code == 429:
                error = ErrorCatalog.AI_RATE_LIMITED
                details = {"message": "OpenAI rate limit exceeded", "retryable": True, "model": self._model}
            elif status_code == 400 and ("model" in error_lower and ("not found" in error_lower or "does not exist" in error_lower)):
                error = ErrorCatalog.AI_INVALID_MODEL
                details = {"message": "Configured OpenAI model is invalid", "retryable": False, "model": self._model}
            elif status_code and status_code >= 500:
                error = ErrorCatalog.AI_SERVICE_UNAVAILABLE
                details = {"message": "OpenAI service unavailable", "retryable": True, "model": self._model}
            else:
                error = ErrorCatalog.AI_SERVICE_UNAVAILABLE
                details = {"message": "AI analysis failed", "retryable": status_code != 400, "model": self._model}
            logger.warning(
                "stock.ai_preload.openai_call_finished trace_id=%s tenant_id=%s store_id=%s success=false timeout=false elapsed_ms=%s error_class=%s status_code=%s model_used=%s",
                trace_id,
                tenant_id,
                store_id,
                elapsed_ms,
                exc.__class__.__name__,
                status_code,
                self._model,
            )
            raise AppError(error, details=details) from exc
        except httpx.HTTPError as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "stock.ai_preload.openai_call_finished trace_id=%s tenant_id=%s store_id=%s success=false timeout=false elapsed_ms=%s error_class=%s model_used=%s",
                trace_id,
                tenant_id,
                store_id,
                elapsed_ms,
                exc.__class__.__name__,
                self._model,
            )
            raise AppError(
                ErrorCatalog.AI_SERVICE_UNAVAILABLE,
                details={"message": "AI analysis failed", "retryable": True, "model": self._model},
            ) from exc

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "stock.ai_preload.openai_call_finished trace_id=%s tenant_id=%s store_id=%s success=true timeout=false elapsed_ms=%s model_used=%s",
            trace_id,
            tenant_id,
            store_id,
            elapsed_ms,
            self._model,
        )

        text_output = data.get("output_text")
        if text_output:
            try:
                return json.loads(text_output)
            except json.JSONDecodeError as exc:
                raise AppError(
                    ErrorCatalog.AI_BAD_RESPONSE,
                    details={"message": "OpenAI returned malformed JSON output", "retryable": False, "model": self._model},
                ) from exc
        output = data.get("output", [])
        for item in output:
            for content_item in item.get("content", []):
                if content_item.get("type") == "output_text":
                    try:
                        return json.loads(content_item.get("text", "{}"))
                    except json.JSONDecodeError as exc:
                        raise AppError(
                            ErrorCatalog.AI_BAD_RESPONSE,
                            details={"message": "OpenAI returned malformed JSON output", "retryable": False, "model": self._model},
                        ) from exc
        raise AppError(
            ErrorCatalog.AI_BAD_RESPONSE,
            details={"message": "AI analysis returned empty output", "retryable": False, "model": self._model},
        )


class StockAiPreloadService:
    def __init__(self, openai_client: OpenAIInventoryClient | None = None) -> None:
        self.openai_client = openai_client or OpenAIInventoryClient()

    def validate_files(self, files: list[UploadedSource]) -> None:
        if len(files) > settings.AI_PRELOAD_MAX_FILES:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "too many files"})
        total_bytes = 0
        for file in files:
            if file.content_type not in SUPPORTED_CONTENT_TYPES:
                raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": f"unsupported file type: {file.content_type}"})
            if len(file.content) > settings.AI_PRELOAD_MAX_FILE_BYTES:
                raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": f"file too large: {file.filename}"})
            total_bytes += len(file.content)
        if total_bytes > settings.AI_PRELOAD_MAX_TOTAL_BYTES:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "total upload size exceeded"})

    def extract_spreadsheet_rows(self, file: UploadedSource) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        warnings: list[dict[str, str]] = []
        rows: list[dict[str, str]] = []
        if file.content_type in {"text/csv", "text/tab-separated-values"}:
            delimiter = "\t" if file.content_type == "text/tab-separated-values" else ","
            reader = csv.DictReader(io.StringIO(file.content.decode("utf-8", errors="ignore")), delimiter=delimiter)
            for idx, row in enumerate(reader, start=2):
                normalized = {str(k or "").strip().lower(): str(v or "").strip() for k, v in row.items()}
                normalized["_row_number"] = str(idx)
                rows.append(normalized)
        else:
            wb = load_workbook(io.BytesIO(file.content), data_only=True)
            for sheet in wb.worksheets:
                values = list(sheet.iter_rows(values_only=True))
                if not values:
                    continue
                headers = [str(v or "").strip().lower() for v in values[0]]
                for idx, value_row in enumerate(values[1:], start=2):
                    normalized = {headers[i]: str(value_row[i] or "").strip() for i in range(len(headers)) if headers[i]}
                    normalized["_row_number"] = str(idx)
                    normalized["_sheet_name"] = sheet.title
                    rows.append(normalized)
        if not rows:
            return rows, warnings
        keys = {k for row in rows for k in row.keys()}
        if any(any(token in key for token in EPC_KEYS) for key in keys):
            warnings.append({"severity": "info", "message": "EPC values were detected but ignored. EPC must be assigned later."})
        if any(any(token in key for token in SALE_KEYS) for key in keys):
            warnings.append({"severity": "info", "message": "Sale price values were detected but not imported. Final sale price must be set later."})
        return rows, warnings

    def extract_docx_text(self, content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            xml_data = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml_data)
        return "\n".join(node.text for node in root.iter() if node.text)

    def parse_decimal(self, value: str | None) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": f"invalid decimal: {value}"}) from exc

    def round_up(self, value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_CEILING) * step

    def apply_pricing(
        self,
        *,
        line: dict[str, Any],
        source_currency: str,
        exchange_rate_to_gtq: Decimal | None,
        pricing_mode: str,
        markup_percent: Decimal | None,
        margin_percent: Decimal | None,
        multiplier: Decimal | None,
        rounding_step: Decimal,
    ) -> dict[str, Any]:
        needs_review = bool(line.get("needs_review", False))
        original_cost = self.parse_decimal(line.get("original_cost"))
        line_currency = (line.get("source_currency") or source_currency or "GTQ").upper()
        if original_cost is not None:
            if line_currency == "GTQ":
                rate = Decimal("1.00")
            else:
                rate = exchange_rate_to_gtq
                if rate is None:
                    needs_review = True
            if rate is not None:
                cost_gtq = (original_cost * rate).quantize(Decimal("0.01"))
                line["cost_gtq"] = format(cost_gtq, "f")
                line["exchange_rate_to_gtq"] = format(rate, "f")
                if pricing_mode == "markup_percent" and markup_percent is not None:
                    base = cost_gtq * (Decimal("1") + (markup_percent / Decimal("100")))
                    line["suggested_price_gtq"] = format(self.round_up(base, rounding_step).quantize(Decimal("0.01")), "f")
                elif pricing_mode == "margin_percent" and margin_percent is not None:
                    base = cost_gtq / (Decimal("1") - (margin_percent / Decimal("100")))
                    line["suggested_price_gtq"] = format(self.round_up(base, rounding_step).quantize(Decimal("0.01")), "f")
                elif pricing_mode == "multiplier" and multiplier is not None:
                    base = cost_gtq * multiplier
                    line["suggested_price_gtq"] = format(self.round_up(base, rounding_step).quantize(Decimal("0.01")), "f")
                elif pricing_mode == "manual":
                    line["suggested_price_gtq"] = None
                    needs_review = True
        line["source_currency"] = line_currency
        line["needs_review"] = needs_review
        return line
