from fastapi.testclient import TestClient

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.services.pos_returns import PosReturnsService
from app.main import create_app


client = TestClient(create_app())


def test_returns_list_empty_200():
    response = client.get('/aris3/pos/returns')
    assert response.status_code == 200
    body = response.json()
    assert body['rows'] == []
    assert body['page'] == 1


def test_returns_detail_404_only_by_id():
    response = client.get('/aris3/pos/returns/not-found')
    assert response.status_code == 404


def test_returns_eligibility_route_not_shadowed(monkeypatch):
    calls = {"get_eligibility": 0, "get_return": 0}

    def _fake_get_eligibility(self, *, sale_id, receipt_number):
        calls["get_eligibility"] += 1
        return {
            "sale_id": sale_id,
            "receipt_number": receipt_number,
            "eligible": True,
            "reason": None,
            "lines": [],
            "allowed_settlement_methods": ["CASH"],
        }

    def _fake_get_return(self, return_id):
        calls["get_return"] += 1
        raise AssertionError(f"Eligibility route was shadowed by return detail route: {return_id}")

    monkeypatch.setattr(PosReturnsService, "get_eligibility", _fake_get_eligibility)
    monkeypatch.setattr(PosReturnsService, "get_return", _fake_get_return)

    sale_id = "aadd2a80-dfa7-45b5-86b4-6df24da6faf1"
    response = client.get(f"/aris3/pos/returns/eligibility?sale_id={sale_id}")

    assert response.status_code == 200
    assert response.json()["sale_id"] == sale_id
    assert calls["get_eligibility"] == 1
    assert calls["get_return"] == 0


def test_returns_detail_route_still_hits_get_return(monkeypatch):
    calls = {"get_return": 0}

    def _fake_get_return(self, return_id):
        calls["get_return"] += 1
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, {"message": "return not found"})

    monkeypatch.setattr(PosReturnsService, "get_return", _fake_get_return)

    return_id = "00000000-0000-0000-0000-000000009999"
    response = client.get(f"/aris3/pos/returns/{return_id}")

    assert response.status_code == 404
    assert calls["get_return"] == 1
