from mcp_server.client import HttpRecorder, InProcessRecorder, get_recorder


def test_inprocess_recorder_writes_to_file(tmp_path):
    recorder = InProcessRecorder()
    file_path = str(tmp_path / "out.txt")
    result = recorder.record("Jane Doe", "ABC123", "9am -> 11am", "t1", file_path=file_path)
    assert result["status"] == "written"
    assert "Jane Doe" in open(file_path).read()


def test_http_recorder_posts_to_configured_endpoint(monkeypatch):
    calls = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"status": "written"}

    def _fake_post(url, json=None, headers=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        calls["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)

    recorder = HttpRecorder(base_url="http://admin.test", api_key="k1")
    result = recorder.record("Jane Doe", "ABC123", "9am -> 11am", "t1")

    assert calls["url"] == "http://admin.test/mcp/write-reservation"
    assert calls["headers"] == {"x-api-key": "k1"}
    assert result["status"] == "written"


def test_get_recorder_defaults_to_inprocess(monkeypatch):
    monkeypatch.delenv("MCP_CLIENT_MODE", raising=False)
    assert isinstance(get_recorder(), InProcessRecorder)