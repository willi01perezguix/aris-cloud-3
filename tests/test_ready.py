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
