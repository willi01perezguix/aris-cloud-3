import io
import uuid

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

    def _mock_extract(self, *, prompt, attachments):
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
