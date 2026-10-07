import mcp_server.reservation_writer as writer_module
from mcp_server.server import write_reservation


def _configure_output(tmp_path, monkeypatch):
    monkeypatch.setattr(writer_module.mcp_settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(writer_module.mcp_settings, "OUTPUT_FILE_PATH", str(tmp_path / "out.txt"))


def test_write_reservation_tool_writes_successfully(tmp_path, monkeypatch):
    _configure_output(tmp_path, monkeypatch)
    result = write_reservation(name="Jane Doe", car_number="ABC123", period="9am -> 11am", approval_time="t1")
    assert result["status"] == "written"


def test_write_reservation_tool_returns_rejected_on_invalid_input(tmp_path, monkeypatch):
    _configure_output(tmp_path, monkeypatch)
    result = write_reservation(name="", car_number="ABC123", period="9am -> 11am")
    assert result["status"] == "rejected"
    assert "error" in result