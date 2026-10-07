import os

from dotenv import load_dotenv

load_dotenv()


class MCPSettings:
    OUTPUT_DIR = os.getenv("MCP_OUTPUT_DIR", "data/reservations")
    OUTPUT_FILE_PATH = os.getenv("MCP_OUTPUT_FILE", os.path.join(OUTPUT_DIR, "confirmed_reservations.txt"))
    API_KEY = os.getenv("MCP_API_KEY", "")
    HTTP_HOST = os.getenv("MCP_HTTP_HOST", "0.0.0.0")
    HTTP_PORT = int(os.getenv("MCP_HTTP_PORT", 8002))


mcp_settings = MCPSettings()