from __future__ import annotations

import json
import time
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


@dataclass
class HttpClient:
    config: ClientConfig
    trace: TraceContext | None = None
    session: requests.Session | None = None
    before_request: RequestHook | None = None
    after_response: ResponseHook | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            adapter = HTTPAdapter(
                pool_connections=self.config.max_connections,
                pool_maxsize=self.config.max_connections,
            )
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

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

        if self.after_response:
            self.after_response(response)
        trace_context.update_from_headers(response.headers)
        if response_hook:
            response_hook(response)
        if response.ok:
            if not response.content:
                return None
            return response.json()

        payload = None
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"message": response.text}
        trace_context.update_from_payload(payload if isinstance(payload, dict) else {})
        raise map_error(response.status_code, payload, trace_context.trace_id)
