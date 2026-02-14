from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.http_client import HttpClient

from aris_control_2.app.context_store import (
    clear_auth_recovery_context,
    clear_context,
    load_auth_recovery_context,
    restore_compatible_context,
    save_auth_recovery_context,
    save_context,
)
from aris_control_2.app.main import _logout_session, _restore_auth_recovery_context
from aris_control_2.app.session_guard import SessionGuard, validate_token
from aris_control_2.app.state import SessionState


def _jwt_with_exp(exp: datetime) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": int(exp.timestamp())}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.sig"


def test_session_guard_redirects_when_token_expired() -> None:
    session = SessionState(access_token=_jwt_with_exp(datetime.now(tz=timezone.utc) - timedelta(minutes=1)))
    invalid_reasons: list[str] = []

    guard = SessionGuard(on_invalid_session=lambda reason: invalid_reasons.append(reason))

    allowed = guard.require_session(session, module="admin_core")

    assert allowed is False
    assert invalid_reasons == ["expired_token"]


def test_http_interceptor_calls_handler_for_401_and_403() -> None:
    events: list[tuple[int | None, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/unauthorized"):
            return httpx.Response(401, json={"code": "AUTH_401", "message": "expired", "trace_id": "trace-401"})
        return httpx.Response(403, json={"code": "AUTH_403", "message": "forbidden", "trace_id": "trace-403"})

    client = HttpClient(client=httpx.Client(base_url="https://example.test/", transport=httpx.MockTransport(handler)))
    client.register_auth_error_handler(lambda error: events.append((error.status_code, error.trace_id or "")))

    for path in ["/unauthorized", "/forbidden"]:
        try:
            client.request("GET", path)
        except ApiError:
            pass

    assert events == [(401, "trace-401"), (403, "trace-403")]


def test_post_login_context_restore_only_when_scope_compatible(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_AUTH_RECOVERY_CONTEXT_PATH", str(tmp_path / "recovery.json"))
    session = SessionState(role="ADMIN", effective_tenant_id="tenant-1", selected_tenant_id="tenant-1")

    save_auth_recovery_context(
        reason="401",
        current_module="stores",
        selected_tenant_id="tenant-1",
        filters_by_module={"stores": {"status": "ACTIVE"}},
        pagination_by_module={"stores": {"page": 2, "page_size": 20}},
    )

    _restore_auth_recovery_context(session)

    assert session.current_module == "stores"
    assert session.selected_tenant_id == "tenant-1"
    assert session.filters_by_module["stores"]["status"] == "ACTIVE"
    assert load_auth_recovery_context() == {}


def test_logout_cleans_sensitive_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_OPERATOR_CONTEXT_PATH", str(tmp_path / "operator-context.json"))
    monkeypatch.setenv("ARIS3_AUTH_RECOVERY_CONTEXT_PATH", str(tmp_path / "recovery-context.json"))

    session = SessionState(
        access_token="token",
        refresh_token="refresh",
        role="SUPERADMIN",
        effective_tenant_id="tenant-1",
        selected_tenant_id="tenant-2",
        filters_by_module={"stores": {"status": "ACTIVE"}},
        pagination_by_module={"stores": {"page": 3, "page_size": 20}},
    )
    save_context(
        session_fingerprint="SUPERADMIN:tenant-1",
        selected_tenant_id="tenant-2",
        filters_by_module=session.filters_by_module,
        pagination_by_module=session.pagination_by_module,
    )
    save_auth_recovery_context(
        reason="401",
        current_module="stores",
        selected_tenant_id="tenant-2",
        filters_by_module=session.filters_by_module,
        pagination_by_module=session.pagination_by_module,
    )

    _logout_session(session)

    assert session.is_authenticated() is False
    assert restore_compatible_context(session_fingerprint="SUPERADMIN:tenant-1") == {}
    assert load_auth_recovery_context() == {}
    clear_context()
    clear_auth_recovery_context()


def test_validate_token_detects_corrupt() -> None:
    validation = validate_token("not-a-jwt")
    assert validation.valid is False
    assert validation.reason == "corrupt_token"
