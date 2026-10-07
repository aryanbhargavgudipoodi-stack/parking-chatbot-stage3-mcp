"""
FastAPI wrapper around the reservation writer -- the "simple MCP server
using Python + FastAPI" alternative explicitly allowed by the spec, and
also a convenient HTTP integration point for the admin agent (Stage 2)
without needing a full MCP client/stdio session.

Secured with:
  - an API key (MCP_API_KEY) sent as the `x-api-key` header on the write
    endpoint
  - a per-client rate limit
  - no client-controlled file path (always writes to the server-configured
    location -- see reservation_writer._resolve_output_path)

Run with: uvicorn mcp_server.api:app --port 8002
Docs: http://localhost:8002/docs
"""
import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from mcp_server.rate_limit import rate_limit
from mcp_server.reservation_writer import InvalidReservationDataError, write_reservation_record

app = FastAPI(title="Parking Reservation MCP Server (FastAPI)")


def verify_api_key(x_api_key: str = Header(default="")):
    expected = os.getenv("MCP_API_KEY", "")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


class ReservationPayload(BaseModel):
    name: str
    car_number: str
    period: str
    approval_time: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/mcp/write-reservation",
    dependencies=[Depends(verify_api_key), Depends(rate_limit)],
)
def write_reservation(payload: ReservationPayload):
    try:
        return write_reservation_record(
            name=payload.name, car_number=payload.car_number,
            period=payload.period, approval_time=payload.approval_time,
        )
    except InvalidReservationDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc))