"""
Real MCP (Model Context Protocol) server exposing a single tool,
`write_reservation`, that records an admin-approved reservation to the
shared output file. Any MCP-compatible client (Claude Desktop,
LangChain's MCP adapter, the official `mcp` client library, this
project's own mcp_server/client.py) can call this tool over stdio.

Run (stdio -- how MCP clients normally launch servers):
    python -m mcp_server.server

Run over SSE instead (if your installed `mcp` SDK version supports it):
    python -m mcp_server.server --sse
"""
import sys

from mcp.server.fastmcp import FastMCP

from mcp_server.reservation_writer import InvalidReservationDataError, write_reservation_record

mcp = FastMCP("parking-reservation-writer")


@mcp.tool()
def write_reservation(name: str, car_number: str, period: str, approval_time: str = "") -> dict:
    """
    Writes a confirmed (admin-approved) parking reservation to the
    reservations file in the format:
        Name | Car Number | Reservation Period | Approval Time

    Args:
        name: full name of the person who made the reservation.
        car_number: the car's license plate number.
        period: the reservation period, e.g. "2025-01-10 09:00 -> 11:00".
        approval_time: ISO-8601 timestamp of when the admin approved the
            request. If omitted, the current UTC time is used.
    """
    try:
        return write_reservation_record(
            name=name, car_number=car_number, period=period,
            approval_time=approval_time or None,
        )
    except InvalidReservationDataError as exc:
        return {"status": "rejected", "error": str(exc)}


if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)