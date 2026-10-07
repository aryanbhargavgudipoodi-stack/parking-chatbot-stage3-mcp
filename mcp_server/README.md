# Stage 3 — MCP Server for Confirmed Reservations

Once the administrator (Stage 2's `AdminAgent`) approves a reservation,
it gets written to a text file:

```text
Name | Car Number | Reservation Period | Approval Time
```

## Three equivalent write paths, one shared core

`mcp_server/reservation_writer.py` is the single source of truth for the
file format and its safety guarantees (input sanitization, path-traversal
protection, file locking + fsync). Three things call into it:

1. **Real MCP server** (`mcp_server/server.py`) — exposes a `write_reservation`
   tool over the Model Context Protocol (stdio transport). Any MCP client
   can call it:

   ```bash
   python -m mcp_server.server
   ```

2. **FastAPI alternative** (`mcp_server/api.py`) — the "simple MCP server
   using Python + FastAPI" explicitly allowed by the spec:

   ```bash
   uvicorn mcp_server.api:app --port 8002
   # docs at http://localhost:8002/docs
   ```

3. **Plain function call** — `write_reservation_record(...)`, used directly
   by `AdminAgent` in the default `MCP_CLIENT_MODE=inprocess` mode — the
   fallback explicitly allowed when a full MCP server isn't needed.

## How AdminAgent uses it

`AdminAgent.apply_decision(request_id, approved=True)` calls
`self.recorder.record(...)` (see `mcp_server/client.py`), where `recorder`
is selected via `MCP_CLIENT_MODE`:

| **Mode**              | **What it does**                                                          |
| --------------------- | ------------------------------------------------------------------------- |
| `inprocess` (default) | calls `write_reservation_record()` directly, no extra process needed      |
| `http`                | POSTs to the FastAPI server at `MCP_HTTP_URL`                             |
| `mcp`                 | talks to the real MCP server over stdio using the official MCP client SDK |

This means **the same approval flow (REST API decision endpoint, or the
admin's natural-language CLI) always results in a file write**, regardless
of which recorder mode is configured.

## Security & reliability

* **No client-controlled file paths** — the output path is always
  server-configured (`MCP_OUTPUT_DIR`/`MCP_OUTPUT_FILE`); requests can
  never specify where to write, which closes off path-traversal attacks.
* **Input sanitization** — rejects empty fields, overly long fields, and
  any `|`/newline characters (which would corrupt the pipe-delimited
  format or let someone inject fake extra lines).
* **API key** (`MCP_API_KEY`) on the FastAPI write endpoint, sent as the
  `x-api-key` header.
* **Rate limiting** on the FastAPI write endpoint (per-client sliding
  window) to blunt abuse/flooding.
* **File locking + fsync** (`filelock`) so concurrent approvals can't
  interleave/corrupt the file, and writes are durably flushed to disk.
* Malformed input is a `422`/rejected result, not a crash — the writer
  never raises an unhandled exception into the admin flow.

## Setup & run

```bash
pip install -r requirements.txt
cp .env.example .env

# option 1: FastAPI server
uvicorn mcp_server.api:app --port 8002

# option 2: real MCP server (stdio)
python -m mcp_server.server

# option 3: nothing extra to run -- MCP_CLIENT_MODE=inprocess (default)
# writes happen directly when AdminAgent.apply_decision(approved=True) runs
```

Check the output:

```bash
cat data/reservations/confirmed_reservations.txt
# Jane Doe | ABC123 | 9am -> 11am | 2025-01-10T09:05:00+00:00
```

## Testing

```bash
pytest tests/test_reservation_writer.py tests/test_mcp_api.py \
       tests/test_mcp_rate_limit.py tests/test_mcp_client.py \
       tests/test_mcp_server_tool.py tests/test_mcp_config.py \
       tests/test_admin_agent.py -v
```
