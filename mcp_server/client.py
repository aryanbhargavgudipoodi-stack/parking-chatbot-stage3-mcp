"""
Recorder abstraction used by the admin agent (Stage 2) to record an
approved reservation once a decision is made. Select via MCP_CLIENT_MODE:
  - "inprocess" (default): calls the writer function directly -- the
    tool/function-call fallback explicitly allowed by the spec.
  - "http": calls the FastAPI wrapper over HTTP.
  - "mcp": calls the real MCP server over stdio using the official MCP
    client SDK.
"""
import os

from mcp_server.reservation_writer import write_reservation_record


class ReservationRecorder:
    def record(self, name: str, car_number: str, period: str,
               approval_time: str = None, file_path: str = None) -> dict:
        raise NotImplementedError


class InProcessRecorder(ReservationRecorder):
    def record(self, name, car_number, period, approval_time=None, file_path=None) -> dict:
        return write_reservation_record(name, car_number, period, approval_time, file_path=file_path)


class HttpRecorder(ReservationRecorder):
    def __init__(self, base_url: str = None, api_key: str = None, timeout: float = 10.0):
        self.base_url = base_url or os.getenv("MCP_HTTP_URL", "http://localhost:8002")
        self.api_key = api_key or os.getenv("MCP_API_KEY", "")
        self.timeout = timeout

    def record(self, name, car_number, period, approval_time=None, file_path=None) -> dict:
        # file_path is intentionally ignored -- the remote server controls
        # where it writes (prevents path-traversal via the API).
        import requests

        headers = {"x-api-key": self.api_key} if self.api_key else {}
        response = requests.post(
            f"{self.base_url}/mcp/write-reservation",
            json={"name": name, "car_number": car_number, "period": period, "approval_time": approval_time},
            headers=headers, timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


class McpStdioRecorder(ReservationRecorder):
    """Talks to the real MCP server over stdio using the official MCP client SDK."""

    def __init__(self, command: str = "python", args=None):
        self.command = command
        self.args = args or ["-m", "mcp_server.server"]

    def record(self, name, car_number, period, approval_time=None, file_path=None) -> dict:
        import asyncio

        return asyncio.run(self._record_async(name, car_number, period, approval_time))

    async def _record_async(self, name, car_number, period, approval_time):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=self.command, args=self.args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "write_reservation",
                    arguments={
                        "name": name, "car_number": car_number,
                        "period": period, "approval_time": approval_time or "",
                    },
                )
                return {"status": "written", "content": result.content}


def get_recorder() -> ReservationRecorder:
    mode = os.getenv("MCP_CLIENT_MODE", "inprocess")
    if mode == "http":
        return HttpRecorder()
    if mode == "mcp":
        return McpStdioRecorder()
    return InProcessRecorder()