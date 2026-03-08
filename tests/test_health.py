def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "aris3"
    assert payload["readiness"] == "live"
    assert payload["trace_id"]
    assert payload["version"]
    assert payload["timestamp"]
