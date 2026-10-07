from fastapi.testclient import TestClient

import mcp_server.reservation_writer as writer_module
from mcp_server.api import app


def _configure_output(tmp_path, monkeypatch):
    monkeypatch.setattr(writer_module.mcp_settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(writer_module.mcp_settings, "OUTPUT_FILE_PATH", str(tmp_path / "out.txt"))


def test_write_reservation_endpoint_success(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    _configure_output(tmp_path, monkeypatch)

    client = TestClient(app)
    response = client.post("/mcp/write-reservation", json={
        "name": "Jane Doe", "car_number": "ABC123", "period": "9am -> 11am",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "written"


def test_write_reservation_endpoint_rejects_invalid_data(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    _configure_output(tmp_path, monkeypatch)

    client = TestClient(app)
    response = client.post("/mcp/write-reservation", json={
        "name": "", "car_number": "ABC123", "period": "9am -> 11am",
    })
    assert response.status_code == 422


def test_write_reservation_endpoint_requires_api_key(monkeypatch):
    monkeypatch.setenv("MCP_API_KEY", "secret123")

    client = TestClient(app)
    response = client.post(
        "/mcp/write-reservation",
        json={"name": "Jane Doe", "car_number": "ABC123", "period": "9am -> 11am"},
        headers={"x-api-key": "wrong"},
    )
    assert response.status_code == 401


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}