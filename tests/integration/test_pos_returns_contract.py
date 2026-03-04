from fastapi.testclient import TestClient

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
