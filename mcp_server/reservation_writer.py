"""
Core reservation-recording logic shared by the MCP server, the FastAPI
wrapper, and the plain-function fallback. Writing to the output file
always goes through this single function, so there's exactly one place
that defines the file format and its safety/reliability guarantees.

File format (one line per confirmed reservation):
    Name | Car Number | Reservation Period | Approval Time
"""
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from mcp_server.config import mcp_settings

_PIPE_OR_NEWLINE = re.compile(r"[|\r\n]")
_MAX_FIELD_LENGTH = 120


class InvalidReservationDataError(ValueError):
    """Raised for malformed/unsafe input -- treat as a client error, not a server failure."""


@dataclass
class ReservationRecord:
    name: str
    car_number: str
    period: str
    approval_time: str

    def as_line(self) -> str:
        return f"{self.name} | {self.car_number} | {self.period} | {self.approval_time}\n"


def _sanitize_field(value: str, field_name: str) -> str:
    if value is None:
        raise InvalidReservationDataError(f"{field_name} is required")
    value = str(value).strip()
    if not value:
        raise InvalidReservationDataError(f"{field_name} must not be empty")
    if len(value) > _MAX_FIELD_LENGTH:
        raise InvalidReservationDataError(f"{field_name} exceeds {_MAX_FIELD_LENGTH} characters")
    if _PIPE_OR_NEWLINE.search(value):
        raise InvalidReservationDataError(
            f"{field_name} must not contain '|' or newline characters (would corrupt the file format)"
        )
    return value


def _resolve_output_path(file_path: str = None) -> Path:
    """
    Resolves the target file path and enforces that it stays inside the
    configured output directory -- clients (HTTP/MCP callers) can never
    control where on disk this writes, which is the main defense against
    path-traversal / arbitrary-file-write abuse.
    """
    allowed_dir = Path(mcp_settings.OUTPUT_DIR).resolve()
    path = Path(file_path or mcp_settings.OUTPUT_FILE_PATH).resolve()

    if allowed_dir != path.parent and allowed_dir not in path.parents:
        raise InvalidReservationDataError(
            f"Refusing to write outside the configured output directory ({allowed_dir})"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_reservation_record(name: str, car_number: str, period: str,
                              approval_time: str = None, file_path: str = None) -> dict:
    """
    Appends one line to the reservations file in the format:
        Name | Car Number | Reservation Period | Approval Time

    Returns a dict describing the write (used as the MCP tool result and
    the REST response body). Raises InvalidReservationDataError on bad
    input. Uses a file lock + fsync so concurrent approvals (e.g. two
    admins approving at the same moment) can't corrupt the file.
    """
    record = ReservationRecord(
        name=_sanitize_field(name, "name"),
        car_number=_sanitize_field(car_number, "car_number"),
        period=_sanitize_field(period, "period"),
        approval_time=_sanitize_field(
            approval_time or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "approval_time",
        ),
    )

    output_path = _resolve_output_path(file_path)
    lock_path = str(output_path) + ".lock"

    with FileLock(lock_path, timeout=10):
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(record.as_line())
            f.flush()
            os.fsync(f.fileno())

    return {
        "status": "written",
        "file": str(output_path),
        "line": record.as_line().rstrip("\n"),
    }