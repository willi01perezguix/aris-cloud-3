from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ..error_mapper import map_error
from ..exceptions import NotFoundError
from ..idempotency import IdempotencyKeys, new_idempotency_keys
from ..models_exports import (
    ExportArtifact,
    ExportListResponse,
    ExportRequest,
    ExportResolvedArtifact,
    ExportStatus,
    ExportTerminalState,
    ExportWaitResult,
)
from .base import BaseClient


@dataclass
class ExportsClient(BaseClient):
    def request_export(
        self,
        payload: ExportRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ExportStatus:
        request = _coerce_model(payload, ExportRequest)
        keys = _resolve_idempotency(
            transaction_id or request.transaction_id, idempotency_key
        )
        request = request.model_copy(update={"transaction_id": keys.transaction_id})
        data = self._request(
            "POST",
            "/aris3/exports",
            json_body=request.model_dump(mode="json", by_alias=True, exclude_none=True),
            headers={"Idempotency-Key": keys.idempotency_key},
        )
        if not isinstance(data, dict):
            raise ValueError("Expected export request response to be a JSON object")
        return ExportStatus.model_validate(data)

    def get_export_status(self, export_id: str) -> ExportStatus:
        data = self._request("GET", f"/aris3/exports/{export_id}")
        if not isinstance(data, dict):
            raise ValueError("Expected export status response to be a JSON object")
        return ExportStatus.model_validate(data)

    def list_recent_exports(self, page_size: int | None = None) -> ExportListResponse:
        params = {"page_size": page_size} if page_size else None
        data = self._request("GET", "/aris3/exports", params=params)
        if not isinstance(data, dict):
            raise ValueError("Expected export list response to be a JSON object")
        return ExportListResponse.model_validate(data)

    def list_exports(self, page_size: int | None = None) -> ExportListResponse:
        return self.list_recent_exports(page_size=page_size)

    def resolve_export_artifact(self, status: ExportStatus) -> ExportResolvedArtifact:
        artifact = status.artifact(api_base_url=self.http.config.api_base_url)
        return ExportResolvedArtifact(
            export_id=status.export_id,
            reference=status.export_id,
            url=artifact.url,
            file_name=artifact.file_name,
            content_type=artifact.content_type,
            file_size_bytes=artifact.file_size_bytes,
        )

    def get_export_artifact(self, export_id: str) -> ExportArtifact:
        status = self.get_export_status(export_id)
        return status.artifact(api_base_url=self.http.config.api_base_url)

    def wait_for_export_ready(
        self,
        export_id: str,
        *,
        timeout_sec: float = 30.0,
        poll_interval_sec: float = 2.0,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ExportWaitResult:
        deadline = time.monotonic() + max(timeout_sec, 0)
        interval = max(poll_interval_sec, 0.2)
        last_status: ExportStatus | None = None

        # Evita leer estado stale desde cache GET durante polling.
        original_get_cache = self.http.enable_get_cache
        self.http.enable_get_cache = False
        try:
            while True:
                if cancel_check and cancel_check():
                    raise TimeoutError(f"Polling cancelled for export {export_id}")
                try:
                    status = self.get_export_status(export_id)
                except NotFoundError:
                    if last_status is not None:
                        return ExportWaitResult(
                            export_id=export_id,
                            outcome=ExportTerminalState.EXPIRED,
                            status=last_status,
                        )
                    raise

                last_status = status
                state = status.status.upper()
                if state in {"READY", "COMPLETED"}:
                    return ExportWaitResult(
                        export_id=export_id,
                        outcome=ExportTerminalState.COMPLETED,
                        status=status,
                    )
                if state in {"FAILED", "ERROR"}:
                    return ExportWaitResult(
                        export_id=export_id,
                        outcome=ExportTerminalState.FAILED,
                        status=status,
                    )
                if state in {"EXPIRED", "NOT_FOUND"}:
                    outcome = (
                        ExportTerminalState.EXPIRED
                        if state == "EXPIRED"
                        else ExportTerminalState.NOT_FOUND
                    )
                    return ExportWaitResult(
                        export_id=export_id,
                        outcome=outcome,
                        status=status,
                    )
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for export {export_id}; "
                        f"last_status={status.status}"
                    )
                time.sleep(interval)
        finally:
            self.http.enable_get_cache = original_get_cache

    def wait_until_ready(
        self,
        export_id: str,
        *,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 2.0,
    ) -> ExportStatus:
        result = self.wait_for_export_ready(
            export_id,
            timeout_sec=timeout_seconds,
            poll_interval_sec=poll_interval_seconds,
        )
        return result.status

    def download_export(self, export_id: str) -> bytes:
        if self.http.session is None:
            raise RuntimeError("HTTP session not initialized")
        trace_context = self.http.trace
        trace_id = trace_context.ensure() if trace_context else None
        headers = {"Accept": "*/*"}
        headers.update(self._auth_headers())
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        response = self.http.session.request(
            method="GET",
            url=self.http._build_url(f"/aris3/exports/{export_id}/download"),
            headers=headers,
            timeout=(
                self.http.config.connect_timeout_seconds,
                self.http.config.read_timeout_seconds,
            ),
            verify=self.http.config.verify_ssl,
        )
        if trace_context:
            trace_context.update_from_headers(response.headers)
        if not response.ok:
            payload = None
            try:
                payload = response.json()
            except ValueError:
                payload = {"message": response.text}
            mapped_trace = trace_context.trace_id if trace_context else None
            raise map_error(
                response.status_code,
                payload if isinstance(payload, dict) else None,
                mapped_trace,
            )
        return response.content


def _resolve_idempotency(
    transaction_id: str | None, idempotency_key: str | None
) -> IdempotencyKeys:
    if transaction_id and idempotency_key:
        return IdempotencyKeys(
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
        )
    generated = new_idempotency_keys()
    return IdempotencyKeys(
        transaction_id=transaction_id or generated.transaction_id,
        idempotency_key=idempotency_key or generated.idempotency_key,
    )


def _coerce_model(value: Any, model_type: type[Any]):
    if isinstance(value, model_type):
        return value
    return model_type.model_validate(value)
