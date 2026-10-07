import importlib

from mcp_server import config as config_module


def test_default_output_dir(monkeypatch):
    monkeypatch.delenv("MCP_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("MCP_OUTPUT_FILE", raising=False)
    importlib.reload(config_module)
    assert config_module.mcp_settings.OUTPUT_DIR == "data/reservations"


def test_output_file_path_derives_from_output_dir_override(monkeypatch):
    monkeypatch.setenv("MCP_OUTPUT_DIR", "/tmp/custom")
    monkeypatch.delenv("MCP_OUTPUT_FILE", raising=False)
    importlib.reload(config_module)
    assert config_module.mcp_settings.OUTPUT_FILE_PATH.startswith("/tmp/custom")

    monkeypatch.delenv("MCP_OUTPUT_DIR", raising=False)
    importlib.reload(config_module)