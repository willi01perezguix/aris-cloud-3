from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter

from .config import ClientConfig
from .error_mapper import map_error
from .exceptions import TransportError
from .tracing import TRACE_HEADER, TraceContext

ResponseHook = Callable[[requests.Response], None]
RequestHook = Callable[[str, str, dict[str, Any]], None]


def _error_type_from_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth"
    if status_code in {400, 404, 422}:
        return "validation"
    if status_code == 409:
        return "conflict"
    if status_code <= 0:
        return "network"
    if status_code >= 500:
        return "internal"
    return "internal"


@dataclass(frozen=True)
class NormalizedError:
    code: str
    message: str
    trace_id: str | None
    type: str


@dataclass
class LastOperation:
    module: str
    operation: str
    duration_ms: int
    result: str
    trace_id: str | None


@dataclass
class HttpClient:
    config: ClientConfig
    trace: TraceContext | None = None
    session: requests.Session | None = None
    before_request: RequestHook | None = None
    after_response: ResponseHook | None = None
    cache_ttl_seconds: float = 3.0
    enable_get_cache: bool = True
    _cache: dict[str, tuple[float, dict[str, Any] | list[Any] | None]] | None = None
    _context_versions: dict[str, int] | None = None
    last_operation: LastOperation | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            adapter = HTTPAdapter(
                pool_connections=self.config.max_connections,
                pool_maxsize=self.config.max_connections,
            )
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        if self._cache is None:
            self._cache = {}
        if self._context_versions is None:
            self._context_versions = {}

    def _build_url(self, path: str) -> str:
        base = self.config.api_base_url.rstrip("/") + "/"
        return urljoin(base, path.lstrip("/"))

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        response_hook: ResponseHook | None = None,
        retry_mutation: bool = False,
        module: str = "unknown",
        operation: str = "unknown",
        use_get_cache: bool = True,
        context_key: str | None = None,
        context_version: int | None = None,
        invalidate_paths: list[str] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        if self.session is None:
            raise RuntimeError("HTTP session not initialized")
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        trace_context = self.trace or TraceContext()
        request_headers[TRACE_HEADER] = trace_context.ensure()

        normalized_method = method.upper()
        url = self._build_url(path)
        request_context = {
            "headers": request_headers,
            "json_body": json_body,
            "params": params,
        }
        if self.before_request:
            self.before_request(normalized_method, url, request_context)

        can_retry = normalized_method in {"GET", "HEAD"} or retry_mutation
        attempts = self.config.retries + 1 if can_retry else 1
        cache_key = self._cache_key(normalized_method, url, request_headers, params)
        should_use_get_cache = (
            self.enable_get_cache and use_get_cache and normalized_method == "GET"
        )
        if should_use_get_cache and cache_key:
            cached = self._read_cache(cache_key)
            if cached is not None:
                self.last_operation = LastOperation(
                    module=module,
                    operation=operation,
                    duration_ms=0,
                    result="success(cache)",
                    trace_id=trace_context.trace_id,
                )
                return cached

        started = time.monotonic()
        if context_key and context_version is None:
            context_version = self.get_context_version(context_key)
        if context_key and not self._context_is_current(context_key, context_version):
            raise TransportError(
                code="REQUEST_CANCELLED",
                message="Request cancelled before dispatch",
                details={"type": "context_switched"},
                trace_id=trace_context.trace_id,
                status_code=0,
                raw_payload=None,
            )
        last_transport_error: Exception | None = None
        response: requests.Response | None = None
        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method=normalized_method,
                    url=url,
                    headers=request_headers,
                    json=json_body,
                    params=params,
                    timeout=(self.config.connect_timeout_seconds, self.config.read_timeout_seconds),
                    verify=self.config.verify_ssl,
                )
            except requests.RequestException as exc:
                last_transport_error = exc
                if attempt >= attempts - 1:
                    trace_context.ensure()
                    raise TransportError(
                        code="TRANSPORT_ERROR",
                        message=str(exc),
                        details={"type": type(exc).__name__},
                        trace_id=trace_context.trace_id,
                        status_code=0,
                        raw_payload=None,
                    ) from exc
            else:
                if response.status_code < 500 or attempt >= attempts - 1:
                    break
                last_transport_error = None
            time.sleep(self.config.retry_backoff_seconds * (2**attempt))

        if response is None:
            raise RuntimeError(f"HTTP request failed without response: {last_transport_error}")

        if context_key and not self._context_is_current(context_key, context_version):
            raise TransportError(
                code="REQUEST_CANCELLED",
                message="Request cancelled due to context switch",
                details={"type": "context_switched"},
                trace_id=trace_context.trace_id,
                status_code=0,
                raw_payload=None,
            )

        if self.after_response:
            self.after_response(response)
        trace_context.update_from_headers(response.headers)
        if response_hook:
            response_hook(response)
        if response.ok:
            if not response.content:
                self._record_operation(module, operation, started, "success", trace_context.trace_id)
                self._invalidate_cache(invalidate_paths or [])
                return None
            parsed = response.json()
            if should_use_get_cache and cache_key:
                self._write_cache(cache_key, parsed)
            if normalized_method != "GET":
                self._invalidate_cache(invalidate_paths or [])
            self._record_operation(module, operation, started, "success", trace_context.trace_id)
            return parsed

        payload = None
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"message": response.text}
        trace_context.update_from_payload(payload if isinstance(payload, dict) else {})
        self._record_operation(module, operation, started, "error", trace_context.trace_id)
        raise map_error(response.status_code, payload, trace_context.trace_id)

    def normalize_error(self, error: Exception) -> NormalizedError:
        if isinstance(error, TransportError):
            return NormalizedError(
                code=error.code,
                message=error.message,
                trace_id=error.trace_id,
                type="network",
            )
        code = getattr(error, "code", "UNKNOWN_ERROR")
        message = getattr(error, "message", str(error))
        trace_id = getattr(error, "trace_id", None)
        status_code = int(getattr(error, "status_code", 0) or 0)
        return NormalizedError(
            code=str(code),
            message=str(message),
            trace_id=trace_id,
            type=_error_type_from_status(status_code),
        )

    def switch_context(self, context_key: str) -> int:
        current = self.get_context_version(context_key)
        new_version = current + 1
        if self._context_versions is None:
            self._context_versions = {}
        self._context_versions[context_key] = new_version
        self.clear_cache()
        return new_version

    def get_context_version(self, context_key: str) -> int:
        if self._context_versions is None:
            self._context_versions = {}
        return self._context_versions.get(context_key, 0)

    def clear_cache(self) -> None:
        if self._cache is not None:
            self._cache.clear()

    def _record_operation(self, module: str, operation: str, started: float, result: str, trace_id: str | None) -> None:
        self.last_operation = LastOperation(
            module=module,
            operation=operation,
            duration_ms=int((time.monotonic() - started) * 1000),
            result=result,
            trace_id=trace_id,
        )

    def _context_is_current(self, context_key: str, context_version: int | None) -> bool:
        if context_version is None:
            return True
        return self.get_context_version(context_key) == context_version

    def _cache_key(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        params: dict[str, Any] | None,
    ) -> str | None:
        if method != "GET":
            return None
        safe_headers = {
            key: value
            for key, value in headers.items()
            if key in {"Authorization", "X-Tenant-ID", "X-App-ID", "X-Device-ID"}
        }
        return json.dumps({"url": url, "headers": safe_headers, "params": params or {}}, sort_keys=True)

    def _read_cache(self, key: str) -> dict[str, Any] | list[Any] | None:
        if self._cache is None:
            return None
        record = self._cache.get(key)
        if not record:
            return None
        expires_at, payload = record
        if time.monotonic() >= expires_at:
            self._cache.pop(key, None)
            return None
        return payload

    def _write_cache(self, key: str, payload: dict[str, Any] | list[Any] | None) -> None:
        if self._cache is None:
            self._cache = {}
        self._cache[key] = (time.monotonic() + self.cache_ttl_seconds, payload)

    def _invalidate_cache(self, paths: list[str]) -> None:
        if self._cache is None:
            return
        if not paths:
            return
        doomed = [key for key in self._cache if any(path in key for path in paths)]
        for key in doomed:
            self._cache.pop(key, None)
