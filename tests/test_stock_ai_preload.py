import io
import uuid

import httpx

from app.aris3.core.config import settings
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import PreloadLine, Store, Tenant, User
from app.aris3.db.seed import run_seed
from app.aris3.services.stock_ai_preload import OpenAIInventoryClient


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_user(db_session, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"user-{suffix}",
        email=f"user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, store, user


def test_ai_preload_analyze_text_and_confirm_creates_preload_session(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload")
    token = _login(client, user.username, "Pass1234!")

    def _mock_extract(self, *, prompt, attachments, **kwargs):
        assert "camisa" in prompt.lower()
        return {
            "document_summary": {"document_type": "invoice", "detected_currency": "USD", "overall_confidence": 0.9},
            "lines": [
                {
                    "sku": "SKU-1",
                    "description": "Camisa negra",
                    "variant_1": "NEGRO",
                    "variant_2": "M",
                    "pool": "BODEGA",
                    "location_code": "BOD-A1",
                    "sellable": False,
                    "quantity": 2,
                    "original_cost": "10.00",
                    "source_currency": "USD",
                    "needs_review": False,
                    "confidence": 0.92,
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(OpenAIInventoryClient, "extract", _mock_extract)

    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "store_id": str(store.id),
            "free_text": "Recibimos 2 camisa negra talla M",
            "source_currency": "USD",
            "exchange_rate_to_gtq": "7.80",
            "pricing_mode": "markup_percent",
            "markup_percent": "40.00",
            "rounding_step": "5.00",
        },
    )
    assert analyze.status_code == 200
    payload = analyze.json()
    assert payload["lines"][0]["cost_gtq"] == "78.00"
    assert payload["lines"][0]["suggested_price_gtq"] == "110.00"
    assert payload["lines"][0]["quantity"] == 2

    confirm = client.post(
        "/aris3/stock/ai/preload/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "extraction_id": payload["extraction_id"],
            "source_currency": "USD",
            "exchange_rate_to_gtq": "7.80",
            "pricing_mode": "markup_percent",
            "markup_percent": "40.00",
            "rounding_step": "5.00",
            "lines": payload["lines"],
        },
    )
    assert confirm.status_code == 200
    result = confirm.json()
    assert result["created_lines_count"] == 2

    lines = db_session.query(PreloadLine).filter(PreloadLine.preload_session_id == uuid.UUID(result["preload_session_id"])).all()
    assert len(lines) == 2
    assert all(line.epc is None for line in lines)
    assert all(line.sale_price is None for line in lines)


def test_ai_preload_spreadsheet_epc_and_sale_warning(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-sheet")
    token = _login(client, user.username, "Pass1234!")

    monkeypatch.setattr(
        OpenAIInventoryClient,
        "extract",
        lambda self, **kwargs: {"document_summary": {"document_type": "spreadsheet"}, "lines": [], "warnings": []},
    )

    csv_content = "SKU,EPC,Descripcion,Venta,Costo,Moneda\nSKU-1,ABC,Prod A,120,10,USD\n"
    files = {"files": ("inventory.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "source_currency": "USD"},
        files=files,
    )
    assert analyze.status_code == 200
    warning_messages = {w["message"] for w in analyze.json()["warnings"]}
    assert any("EPC values were detected" in message for message in warning_messages)
    assert any("Sale price values were detected" in message for message in warning_messages)


def test_ai_preload_confirm_rejects_missing_exchange_rate_for_non_gtq(client, db_session):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-rate")
    token = _login(client, user.username, "Pass1234!")
    confirm = client.post(
        "/aris3/stock/ai/preload/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_currency": "USD",
            "pricing_mode": "manual",
            "lines": [
                {
                    "row_key": "1",
                    "sku": "SKU-1",
                    "description": "Producto",
                    "quantity": 1,
                    "original_cost": "10.00",
                    "source_currency": "USD",
                    "needs_review": True,
                }
            ],
        },
    )
    assert confirm.status_code == 422


def test_ai_preload_analyze_missing_openai_api_key_returns_controlled_json(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-missing-key")
    token = _login(client, user.username, "Pass1234!")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "2 camisas", "source_currency": "USD"},
    )
    assert analyze.status_code == 422
    payload = analyze.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["details"]["message"] == "OPENAI_API_KEY is not configured"


def test_ai_preload_analyze_openai_timeout_returns_controlled_json(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-timeout")
    token = _login(client, user.username, "Pass1234!")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    def _mock_timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx, "post", _mock_timeout)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "2 camisas", "source_currency": "USD"},
    )
    assert analyze.status_code == 504
    payload = analyze.json()
    assert payload["code"] == "AI_SERVICE_TIMEOUT"
    assert payload["details"]["retryable"] is True


def test_ai_preload_analyze_invalid_model_returns_controlled_json(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-invalid-model")
    token = _login(client, user.username, "Pass1234!")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_INVENTORY_MODEL", "bad model !")

    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "2 camisas", "source_currency": "USD"},
    )
    assert analyze.status_code == 422
    payload = analyze.json()
    assert payload["code"] == "AI_INVALID_MODEL"


def test_ai_preload_analyze_invalid_api_key_returns_controlled_json(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-auth-failed")
    token = _login(client, user.username, "Pass1234!")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "bad-key")

    def _mock_http_error(*args, **kwargs):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(401, request=request, text='{"error":{"message":"invalid_api_key"}}')
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr(httpx, "post", _mock_http_error)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "2 camisas", "source_currency": "USD"},
    )
    assert analyze.status_code == 401
    payload = analyze.json()
    assert payload["code"] == "AI_AUTH_FAILED"


def test_ai_preload_analyze_rate_limit_returns_controlled_json(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-rate-limit")
    token = _login(client, user.username, "Pass1234!")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    def _mock_http_error(*args, **kwargs):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(429, request=request, text='{"error":{"message":"rate_limit"}}')
        raise httpx.HTTPStatusError("rate limit", request=request, response=response)

    monkeypatch.setattr(httpx, "post", _mock_http_error)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "2 camisas", "source_currency": "USD"},
    )
    assert analyze.status_code == 429
    payload = analyze.json()
    assert payload["code"] == "AI_RATE_LIMITED"


def test_ai_preload_analyze_malformed_output_returns_controlled_json(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-malformed")
    token = _login(client, user.username, "Pass1234!")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    def _mock_post(*args, **kwargs):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        return httpx.Response(200, request=request, json={"output_text": "{not json"})

    monkeypatch.setattr(httpx, "post", _mock_post)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "2 camisas", "source_currency": "USD"},
    )
    assert analyze.status_code == 502
    payload = analyze.json()
    assert payload["code"] == "AI_BAD_RESPONSE"


def test_ai_preload_analyze_text_only_response_excludes_epc_and_sale_fields(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-text-only")
    token = _login(client, user.username, "Pass1234!")

    def _mock_extract(self, *, prompt, attachments, **kwargs):
        assert attachments == []
        return {
            "document_summary": {"document_type": "other", "detected_currency": "USD", "overall_confidence": 0.9},
            "lines": [
                {
                    "sku": "SKU-TEXT-1",
                    "description": "Camisa negra",
                    "variant_1": "NEGRO",
                    "variant_2": "M",
                    "pool": "BODEGA",
                    "location_code": "BODEGA-A1",
                    "sellable": False,
                    "quantity": 12,
                    "original_cost": "10.00",
                    "source_currency": "USD",
                    "needs_review": False,
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(OpenAIInventoryClient, "extract", _mock_extract)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "store_id": str(store.id),
            "free_text": "12 camisas negras talla M costo USD 10.00 cada una",
            "document_type": "other",
            "source_currency": "USD",
            "exchange_rate_to_gtq": "7.80",
            "pricing_mode": "markup_percent",
            "markup_percent": "40",
            "rounding_step": "5.00",
        },
    )
    assert analyze.status_code == 200
    line = analyze.json()["lines"][0]
    assert line["original_cost"] == "10.00"
    assert line["source_currency"] == "USD"
    assert line["exchange_rate_to_gtq"] == "7.80"
    assert line["cost_gtq"] == "78.00"
    assert line["suggested_price_gtq"] == "110.00"
    assert "epc" not in line
    assert "sale_price" not in line
    assert "venta" not in line


def test_ai_preload_analyze_without_files_field_behaves_as_text_only(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-empty-files")
    token = _login(client, user.username, "Pass1234!")

    def _mock_extract(self, *, attachments, **kwargs):
        assert attachments == []
        return {"document_summary": {}, "lines": [], "warnings": []}

    monkeypatch.setattr(OpenAIInventoryClient, "extract", _mock_extract)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "solo texto", "source_currency": "USD"},
    )
    assert analyze.status_code == 200
    assert analyze.json()["total_lines"] == 0
