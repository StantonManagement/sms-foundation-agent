from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok_and_version():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert isinstance(data["version"], str) and data["version"]
    assert data["checks"]["config"] is True
    assert data["checks"]["db"] in (True, False, "unknown")

