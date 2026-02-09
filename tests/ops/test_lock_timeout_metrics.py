from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.aris3.core.errors import setup_exception_handlers
from app.aris3.core.metrics import metrics


def test_lock_timeout_increments_metric():
    metrics.reset()
    app = FastAPI()
    setup_exception_handlers(app)

    @app.get("/lock-timeout")
    def lock_timeout():
        raise OperationalError("SELECT 1", {}, Exception("lock timeout"))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/lock-timeout")

    assert response.status_code == 409
    assert response.json()["code"] == "LOCK_TIMEOUT"

    snapshot = metrics.render()
    content = snapshot.content.decode("utf-8")
    if metrics.enabled:
        assert "lock_wait_timeout_total" in content
    else:
        assert "metrics_disabled" in content
