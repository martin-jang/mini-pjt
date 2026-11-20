from fastapi.testclient import TestClient

from legacy2next.api import create_app
from legacy2next.config import AgentConfig


def test_health_and_cors():
    client = TestClient(create_app(AgentConfig()))
    res = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
