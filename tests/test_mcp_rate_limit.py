from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import mcp_server.rate_limit as rl
from mcp_server.rate_limit import _hits, rate_limit


def _build_app():
    app = FastAPI()

    @app.get("/limited", dependencies=[Depends(rate_limit)])
    def limited():
        return {"ok": True}

    return app


def test_rate_limit_allows_requests_under_the_limit():
    _hits.clear()
    client = TestClient(_build_app())
    for _ in range(5):
        assert client.get("/limited").status_code == 200


def test_rate_limit_blocks_after_exceeding_window(monkeypatch):
    monkeypatch.setattr(rl, "_MAX_REQUESTS_PER_WINDOW", 3)
    _hits.clear()

    client = TestClient(_build_app())
    for _ in range(3):
        assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 429