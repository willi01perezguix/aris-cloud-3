import io
import uuid

import httpx

from app.aris3.core.config import settings
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import CatalogProduct, CatalogProductCostHistory, PreloadLine, StockAiExtraction, StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed
from app.aris3.routers import stock as stock_router
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


def test_ai_confirm_catalog_only_creates_catalog_without_stock(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "ai-catalog-only")
    token = _login(client, user.username, "Pass1234!")
    confirm = client.post(
        "/aris3/stock/ai/preload/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_currency": "GTQ",
            "pricing_mode": "manual",
            "confirm_mode": "CATALOG_ONLY",
            "lines": [
                {
                    "row_key": "1",
                    "sku": "SKU-CAT-1",
                    "description": "Producto catalogo",
                    "variant_1": "NEGRO",
                    "variant_2": "M",
                    "quantity": 1,
                    "cost_gtq": "111.38",
                    "suggested_price_gtq": "160.00",
                    "needs_review": False,
                }
            ],
        },
    )
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["preload_session_id"] is None
    assert payload["created_lines_count"] == 0
    assert payload["catalog_created_count"] == 1
    assert db_session.query(CatalogProduct).filter(CatalogProduct.tenant_id == tenant.id).count() == 1
    assert db_session.query(PreloadLine).filter(PreloadLine.tenant_id == tenant.id).count() == 0
    assert db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).count() == 0


def test_ai_confirm_catalog_and_preload_updates_existing_catalog_and_links_preload_line(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "ai-cat-preload-update")
    token = _login(client, user.username, "Pass1234!")

    existing = CatalogProduct(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku="SKU-EXIST-1",
        normalized_sku="SKU-EXIST-1",
        variant_1="NEGRO",
        normalized_variant_1="NEGRO",
        variant_2="M",
        normalized_variant_2="M",
        description="Producto anterior",
        last_cost_gtq="100.00",
        suggested_price_gtq="150.00",
    )
    db_session.add(existing)
    db_session.commit()

    confirm = client.post(
        "/aris3/stock/ai/preload/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_currency": "GTQ",
            "pricing_mode": "manual",
            "confirm_mode": "CATALOG_AND_PRELOAD",
            "lines": [
                {
                    "row_key": "1",
                    "sku": "SKU-EXIST-1",
                    "description": "Producto actualizado",
                    "variant_1": "NEGRO",
                    "variant_2": "M",
                    "quantity": 1,
                    "cost_gtq": "111.38",
                    "suggested_price_gtq": "160.00",
                    "needs_review": False,
                }
            ],
        },
    )
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["catalog_created_count"] == 0
    assert payload["catalog_updated_count"] == 1
    assert payload["created_lines_count"] == 1

    session = client.get(
        f"/aris3/stock/preload-sessions/{payload['preload_session_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert session.status_code == 200
    line = session.json()["lines"][0]
    assert line["catalog_product_id"] == str(existing.id)
    assert line["epc"] is None
    assert line["sale_price"] is None
    assert db_session.query(CatalogProduct).filter(CatalogProduct.tenant_id == tenant.id, CatalogProduct.sku == "SKU-EXIST-1").count() == 1


def test_ai_confirm_catalog_and_preload_creates_catalog_and_links_preload_line(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "ai-cat-preload-create")
    token = _login(client, user.username, "Pass1234!")

    confirm = client.post(
        "/aris3/stock/ai/preload/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_currency": "GTQ",
            "pricing_mode": "manual",
            "confirm_mode": "CATALOG_AND_PRELOAD",
            "lines": [
                {
                    "row_key": "1",
                    "sku": "SKU-NEW-1",
                    "description": "Producto nuevo",
                    "variant_1": "BLANCO",
                    "variant_2": "S",
                    "quantity": 1,
                    "cost_gtq": "111.38",
                    "suggested_price_gtq": "160.00",
                    "needs_review": False,
                }
            ],
        },
    )
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["catalog_created_count"] == 1
    assert payload["catalog_updated_count"] == 0
    assert payload["created_lines_count"] == 1

    session = client.get(
        f"/aris3/stock/preload-sessions/{payload['preload_session_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert session.status_code == 200
    line = session.json()["lines"][0]
    assert line["catalog_product_id"] is not None

    product = db_session.query(CatalogProduct).filter(CatalogProduct.tenant_id == tenant.id, CatalogProduct.sku == "SKU-NEW-1").one()
    assert line["catalog_product_id"] == str(product.id)


def test_preload_save_keeps_catalog_product_id_from_catalog_and_preload_confirm(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "ai-cat-preload-save")
    token = _login(client, user.username, "Pass1234!")

    confirm = client.post(
        "/aris3/stock/ai/preload/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_currency": "GTQ",
            "pricing_mode": "manual",
            "confirm_mode": "CATALOG_AND_PRELOAD",
            "lines": [
                {
                    "row_key": "1",
                    "sku": "SKU-SAVE-1",
                    "description": "Producto guardado",
                    "quantity": 1,
                    "cost_gtq": "111.38",
                    "suggested_price_gtq": "160.00",
                    "needs_review": False,
                }
            ],
        },
    )
    assert confirm.status_code == 200
    session_payload = client.get(
        f"/aris3/stock/preload-sessions/{confirm.json()['preload_session_id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    line = session_payload["lines"][0]
    assert line["catalog_product_id"] is not None

    patched = client.patch(
        f"/aris3/stock/preload-lines/{line['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"sale_price": "160.00"},
    )
    assert patched.status_code == 200

    saved = client.post(
        f"/aris3/stock/preload-lines/{line['id']}/save",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert saved.status_code == 200

    created_stock = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id, StockItem.sku == "SKU-SAVE-1").one()
    assert str(created_stock.catalog_product_id) == line["catalog_product_id"]


def test_ai_confirm_create_preload_only_keeps_catalog_product_id_null(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "ai-preload-only-catalog-id")
    token = _login(client, user.username, "Pass1234!")

    confirm = client.post(
        "/aris3/stock/ai/preload/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_currency": "GTQ",
            "pricing_mode": "manual",
            "confirm_mode": "CREATE_PRELOAD_ONLY",
            "lines": [
                {
                    "row_key": "1",
                    "sku": "SKU-PRELOAD-ONLY-1",
                    "description": "Solo precarga",
                    "quantity": 1,
                    "cost_gtq": "111.38",
                    "suggested_price_gtq": "160.00",
                    "needs_review": False,
                }
            ],
        },
    )
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["catalog_created_count"] == 0
    assert payload["catalog_updated_count"] == 0
    session = client.get(
        f"/aris3/stock/preload-sessions/{payload['preload_session_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert session.status_code == 200
    assert session.json()["lines"][0]["catalog_product_id"] is None
    assert db_session.query(CatalogProduct).filter(CatalogProduct.tenant_id == tenant.id).count() == 0


def test_catalog_bulk_upsert_changed_cost_sets_review_without_overwriting_sale_price(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "catalog-bulk-upsert")
    token = _login(client, user.username, "Pass1234!")

    first = client.post(
        "/aris3/catalog/products/bulk-upsert",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_type": "IMPORT",
            "lines": [
                {
                    "sku": "SKU-COST-1",
                    "variant_1": "BLACK",
                    "variant_2": "M",
                    "description": "Camisa",
                    "cost_gtq": "111.38",
                    "suggested_price_gtq": "160.00",
                }
            ],
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/aris3/catalog/products/bulk-upsert",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_type": "IMPORT",
            "lines": [
                {
                    "sku": "SKU-COST-1",
                    "variant_1": "BLACK",
                    "variant_2": "M",
                    "description": "Camisa nueva compra",
                    "cost_gtq": "125.00",
                    "suggested_price_gtq": "175.00",
                }
            ],
        },
    )
    assert second.status_code == 200
    assert second.json()["created_count"] == 0
    assert second.json()["updated_count"] == 1

    product = db_session.query(CatalogProduct).filter(CatalogProduct.tenant_id == tenant.id, CatalogProduct.sku == "SKU-COST-1").one()
    product.default_sale_price_gtq = 160
    db_session.add(product)
    db_session.commit()

    third = client.post(
        "/aris3/catalog/products/upsert",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_type": "MANUAL",
            "line": {
                "sku": "SKU-COST-1",
                "variant_1": "BLACK",
                "variant_2": "M",
                "cost_gtq": "130.00",
                "suggested_price_gtq": "180.00",
            },
        },
    )
    assert third.status_code == 200
    db_session.refresh(product)
    assert str(product.last_cost_gtq) == "130.00"
    assert str(product.suggested_price_gtq) == "180.00"
    assert str(product.default_sale_price_gtq) == "160.00"
    assert product.price_review_required is True
    assert db_session.query(CatalogProductCostHistory).filter(CatalogProductCostHistory.catalog_product_id == product.id).count() == 3


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
    assert payload["details"]["text_only"] is True
    assert payload["details"]["files_count"] == 0
    assert payload["details"]["large_input"] is False


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


def test_ai_preload_text_only_openai_request_uses_valid_responses_payload(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_INVENTORY_MODEL", "gpt-4.1-mini")
    captured: dict = {}

    def _mock_post(url, *, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        request = httpx.Request("POST", url)
        return httpx.Response(200, request=request, json={"output_text": '{"document_summary":{},"pricing_context":{},"lines":[],"warnings":[]}'})

    monkeypatch.setattr(httpx, "post", _mock_post)
    client = OpenAIInventoryClient()
    client.extract(
        prompt="12 camisas negras talla M costo USD 10.00 cada una",
        attachments=[],
        trace_id="trace-test",
        tenant_id="tenant-1",
        store_id="store-1",
        document_type="other",
    )
    payload = captured["json"]
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["name"] == "inventory_preload_extraction"
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["schema"]["additionalProperties"] is False
    user_content = payload["input"][1]["content"]
    assert len(user_content) == 1
    assert user_content[0]["type"] == "input_text"
    assert "input_file" not in str(payload)


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
    assert payload["code"] == "AI_RESPONSE_INVALID"


def test_ai_preload_analyze_openai_400_returns_ai_request_invalid(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-request-invalid")
    token = _login(client, user.username, "Pass1234!")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    def _mock_http_error(*args, **kwargs):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(
            400,
            request=request,
            json={
                "error": {
                    "message": "Invalid schema for response_format",
                    "type": "invalid_request_error",
                    "param": "text.format.schema",
                    "code": "invalid_json_schema",
                }
            },
        )
        raise httpx.HTTPStatusError("bad request", request=request, response=response)

    monkeypatch.setattr(httpx, "post", _mock_http_error)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "2 camisas", "source_currency": "USD"},
    )
    assert analyze.status_code == 422
    payload = analyze.json()
    assert payload["code"] == "AI_REQUEST_INVALID"
    assert payload["details"]["provider_status"] == 400
    assert payload["details"]["provider_error_type"] == "invalid_request_error"
    assert payload["details"]["provider_error_code"] == "invalid_json_schema"
    assert payload["details"]["provider_error_param"] == "text.format.schema"


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


def test_ai_preload_excel_like_template_maps_canonical_fields(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-excel-like")
    token = _login(client, user.username, "Pass1234!")

    monkeypatch.setattr(
        OpenAIInventoryClient,
        "extract",
        lambda self, **kwargs: {"document_summary": {"document_type": "spreadsheet"}, "lines": [], "warnings": []},
    )

    csv_content = (
        "SKU,Descripción,Talla,Color,Cantidad,Precio Costo (Q),Precio (USD),Precio Venta Sugerido (Q),Precio Final (Q),"
        "Número de Pedido,Fecha Pedido,Categoría,Estilo,Marca,Ubicación\n"
        "SKU-9,Camisa deportiva,M,Negro,2,80.00,10.00,120.00,130.00,PO-77,2026-03-01,Ropa,Sport,ARIS,EN TRANSITO\n"
    )
    files = {"files": ("supplier.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "source_currency": "USD", "exchange_rate_to_gtq": "7.80", "pricing_mode": "manual"},
        files=files,
    )
    assert analyze.status_code == 200
    line = analyze.json()["lines"][0]
    assert line["sku"] == "SKU-9"
    assert line["description"] == "Camisa deportiva"
    assert line["color"] == "Negro"
    assert line["size"] == "M"
    assert line["quantity"] == 2
    assert line["cost_gtq"] == "80.00"
    assert line["original_cost"] == "10.00"
    assert line["source_currency"] == "USD"
    assert line["suggested_price_gtq"] == "120.00"
    assert line["reference_price_gtq"] == "130.00"
    assert line["source_order_number"] == "PO-77"
    assert line["source_order_date"] == "2026-03-01"
    assert "epc" not in line
    assert "sale_price" not in line


def test_ai_preload_symbol_currency_and_shein_price_behavior(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-shein")
    token = _login(client, user.username, "Pass1234!")

    def _mock_extract(self, **kwargs):
        return {
            "document_summary": {"document_type": "other"},
            "lines": [
                {
                    "sku": "SHEIN-1",
                    "description": "Top deportivo",
                    "variant_1": "Azul",
                    "variant_2": "S",
                    "quantity": 1,
                    "original_cost": "12.00",
                    "source_currency": "unknown",
                    "reference_price_original": "18.00",
                    "sellable": True,
                    "needs_review": True,
                }
            ],
            "warnings": [{"severity": "warning", "message": "Confirmar moneda antes de calcular Costo(Q)."}],
        }

    monkeypatch.setattr(OpenAIInventoryClient, "extract", _mock_extract)
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": "SHEIN pedido #1 precio $12 y precio $18", "source_currency": "GTQ"},
    )
    assert analyze.status_code == 200
    payload = analyze.json()
    line = payload["lines"][0]
    assert line["source_currency"] == "UNKNOWN"
    assert line["reference_price_original"] == "18.00"
    assert line["sellable"] is True
    assert any("Confirmar moneda" in w["message"] for w in payload["warnings"])


def test_ai_preload_shein_order_text_sets_reference_price_defaults_and_document_summary(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-shein-order-detail")
    token = _login(client, user.username, "Pass1234!")

    def _mock_extract(self, **kwargs):
        return {
            "document_summary": {
                "document_type": "other",
                "detected_currency": "USD",
                "document_number": None,
                "document_date": None,
            },
            "lines": [
                {
                    "sku": "sz2304202919366817",
                    "description": "SHEIN MOD Vestido camisero con estampado floral de lazo para primavera y verano",
                    "variant_1": "Multicolor",
                    "variant_2": "XS",
                    "color": "Multicolor",
                    "size": "XS",
                    "brand": "SHEIN MOD",
                    "category": "Vestido",
                    "style": "camisero",
                    "logistics_status": "Enviado",
                    "sellable": True,
                    "quantity": 1,
                    "source_order_number": "GSH16W13000N6RC",
                    "source_order_date": "2026-02-22",
                    "original_cost": "14.28",
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
            "document_type": "other",
            "source_currency": "USD",
            "exchange_rate_to_gtq": "7.80",
            "pricing_mode": "markup_percent",
            "markup_percent": "40",
            "rounding_step": "5.00",
            "free_text": (
                "Núm. de pedido GSH16W13000N6RC. Fecha 22 Feb 2026. Producto: SHEIN MOD Vestido camisero "
                "con estampado floral de lazo para primavera y verano. Multicolor / XS. Cantidad 1. "
                "SKU: sz2304202919366817. Importe $14.28 $43.16. Estado Enviado."
            ),
        },
    )
    assert analyze.status_code == 200
    payload = analyze.json()
    line = payload["lines"][0]

    assert payload["document_summary"]["document_number"] == "GSH16W13000N6RC"
    assert payload["document_summary"]["document_date"] == "2026-02-22"
    assert line["source_order_number"] == "GSH16W13000N6RC"
    assert line["source_order_date"] == "2026-02-22"
    assert line["original_cost"] == "14.28"
    assert line["reference_price_original"] == "43.16"
    assert line["reference_price_gtq"] == "336.65"
    assert line.get("sale_price") is None
    assert line["pool"] == "BODEGA"
    assert line["location_code"] == "RECEPCION"
    assert line["sellable"] is True
    assert line["logistics_status"] == "Enviado"
    assert any("Segundo importe detectado como precio de referencia" in w["message"] for w in payload["warnings"])


def test_ai_preload_sellable_rules_only_explicit_phrases_force_false(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-sellable-rules")
    token = _login(client, user.username, "Pass1234!")

    monkeypatch.setattr(
        OpenAIInventoryClient,
        "extract",
        lambda self, **kwargs: {"document_summary": {"document_type": "spreadsheet"}, "lines": [], "warnings": []},
    )
    csv_content = "SKU,Descripcion,Cantidad,Precio Costo (Q),Ubicación\nSKU-1,Producto normal en transito,1,10.00,EN TRANSITO\nSKU-2,Producto dañado,1,10.00,BOD-A1\n"
    files = {"files": ("sellable.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "source_currency": "GTQ"},
        files=files,
    )
    assert analyze.status_code == 200
    lines = analyze.json()["lines"]
    assert lines[0]["sellable"] is True
    assert lines[0]["logistics_status"] == "EN_TRANSITO"
    assert lines[1]["sellable"] is False
    assert lines[1]["needs_review"] is True


def test_ai_preload_long_shein_text_uses_deterministic_parser_without_openai(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-long-shein-parser")
    token = _login(client, user.username, "Pass1234!")

    def _should_not_call(*args, **kwargs):
        raise AssertionError("OpenAI extract should not be called for deterministic SHEIN parse")

    monkeypatch.setattr(OpenAIInventoryClient, "extract", _should_not_call)
    long_text = (
        "Núm. de pedido\nGSH16U13F000644\nFecha\n21 Feb 2026\nProductos Cantidad SKU Importe Estado Acción\n"
        "SHEIN SXY Vestido vaquero largo...\nAzul lavado medio / XS\n1 SKU: sz2401176811723523\n$33.15\n$86.91\nEnviado\n"
        "SHEIN SXY Vestido vaquero largo...\nAzul lavado medio / S\n1 SKU: sz2401176811723524\n$30.15\n$82.91\nEnviado\n"
    )
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": long_text, "source_currency": "USD", "exchange_rate_to_gtq": "7.80"},
    )
    assert analyze.status_code == 200
    payload = analyze.json()
    assert payload["status"] == "DRAFT"
    assert payload["total_lines"] == 2
    first = payload["lines"][0]
    assert first["sku"] == "sz2401176811723523"
    assert first["quantity"] == 1
    assert first["original_cost"] == "33.15"
    assert first["reference_price_original"] == "86.91"
    assert first["variant_1"] == "Azul lavado medio"
    assert first["variant_2"] == "XS"
    assert first["sellable"] is True
    assert first["logistics_status"] == "Enviado"
    assert first["pool"] == "BODEGA"
    assert first["location_code"] == "RECEPCION"


def test_ai_preload_long_non_shein_returns_processing_and_get_shows_processing(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-long-processing")
    token = _login(client, user.username, "Pass1234!")

    def _no_background(*args, **kwargs):
        return None

    monkeypatch.setattr(stock_router, "_run_large_ai_preload_extraction", _no_background)
    long_non_shein = ("texto inventario sin patrones shein " * 300) + " SKU: A1 SKU: A2 SKU: A3 SKU: A4 SKU: A5"
    analyze = client.post(
        "/aris3/stock/ai/preload/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"store_id": str(store.id), "free_text": long_non_shein, "source_currency": "USD"},
    )
    assert analyze.status_code == 200
    payload = analyze.json()
    assert payload["status"] == "PROCESSING"
    extraction_id = payload["extraction_id"]

    get_resp = client.get(
        f"/aris3/stock/ai/preload/{extraction_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "PROCESSING"


def test_ai_preload_get_after_background_completion_returns_lines(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "ai-preload-completed")
    token = _login(client, user.username, "Pass1234!")
    extraction = StockAiExtraction(
        tenant_id=_tenant.id,
        store_id=store.id,
        created_by_user_id=user.id,
        source_currency="USD",
        pricing_mode="manual",
        rounding_step="1.00",
        status="COMPLETED",
        raw_ai_result={"document_summary": {"document_type": "other"}},
        normalized_result={"lines": [{"row_key": "1", "sku": "SKU-COMPLETE", "description": "Producto", "quantity": 1, "source_currency": "USD", "needs_review": False}]},
        warnings=[],
        model_used="gpt-4.1-mini",
    )
    db_session.add(extraction)
    db_session.commit()

    get_resp = client.get(f"/aris3/stock/ai/preload/{extraction.id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 200
    payload = get_resp.json()
    assert payload["status"] == "COMPLETED"
    assert payload["total_lines"] == 1
