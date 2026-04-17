from app.main import app


def test_pos_advances_endpoints_are_published_in_openapi():
    paths = app.openapi()["paths"]

    expected = {
        "/aris3/pos/advances": {"get", "post"},
        "/aris3/pos/advances/{advance_id}": {"get"},
        "/aris3/pos/advances/lookup": {"get"},
        "/aris3/pos/advances/{advance_id}/actions": {"post"},
        "/aris3/pos/advances/alerts": {"get"},
    }

    for path, methods in expected.items():
        assert path in paths
        assert methods.issubset(set(paths[path].keys()))
