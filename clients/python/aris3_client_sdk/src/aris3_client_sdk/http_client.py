from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ClientConfig
from .error_mapper import map_error
from .tracing import TRACE_HEADER, TraceContext

ResponseHook = Callable[[requests.Response], None]


@dataclass
class HttpClient:
    config: ClientConfig
    trace: TraceContext | None = None
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            retry = Retry(
                total=self.config.retries,
                backoff_factor=self.config.retry_backoff_seconds,
                status_forcelist=(502, 503, 504),
                allowed_methods=("GET", "HEAD", "OPTIONS"),
            )
            adapter = HTTPAdapter(max_retries=retry)
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
    ) -> dict[str, Any] | list[Any] | None:
        if self.session is None:
            raise RuntimeError("HTTP session not initialized")
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        trace_context = self.trace or TraceContext()
        request_headers[TRACE_HEADER] = trace_context.ensure()

        response = self.session.request(
            method=method.upper(),
            url=self._build_url(path),
            headers=request_headers,
            json=json_body,
            params=params,
            timeout=(self.config.connect_timeout_seconds, self.config.read_timeout_seconds),
            verify=self.config.verify_ssl,
        )
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
