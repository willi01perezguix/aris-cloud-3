from app.aris3.db.session import get_db

def test_ready(client):
    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "aris3"
    assert payload["readiness"] == "ready"
    assert payload["trace_id"]
    assert payload["version"]
    assert payload["timestamp"]


def test_ready_returns_503_when_db_unavailable(client):
    class _BrokenDb:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("db unavailable")

    def _broken_db_dep():
        yield _BrokenDb()

    client.app.dependency_overrides[get_db] = _broken_db_dep
    try:
        response = client.get("/ready")
    finally:
        client.app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "DB_UNAVAILABLE"
    assert payload["trace_id"]
