# Parking Reservation Chatbot — Stage 3 (Admin Approval + MCP Storage)

A parking assistant that answers questions about parking information,
hours, prices, availability, and location; collects reservation details;
routes reservations to an administrator for approval; and records approved
reservations through an MCP-compatible file writer.

## Architecture

```
PDFs (data/pdfs/*.pdf)
   │  PyPDFLoader (per-page) → merge into full doc text + page-offset map
   ▼
SemanticChunker (meaning-based splits; falls back to
RecursiveCharacterTextSplitter if unavailable)
   │
   ├──► metadata DB (SQLite: source_documents, document_chunks)  ← source of truth
   │
   ▼
Vector DB (Milvus, auto-fallback to Chroma)
   │
   ▼
RagChain: intent classification → static_info (vector search) |
          dynamic_info (SQL: hours/prices/availability) | reservation
   │
   ▼
ParkingChatbot: PII guardrail (Presidio) on input + output,
                reservation slot-filling, logging
  │
  ├──► AdminAgent: stores pending requests, notifies administrator,
  │                supports approval/refusal through CLI or REST API
  │
  └──► approved reservation → ReservationRecorder → MCP server / FastAPI /
                      in-process writer → confirmed_reservations.txt
```

Static knowledge (general info, location, booking process, policies) comes
from PDFs. Dynamic data (live hours/prices/availability) comes from a
separate SQLite table (`src/sql_db.py`), reflecting the optional
static/dynamic split from the spec.

## Project structure

```
parking-chatbot/
├── src/
│   ├── config.py              # centralized settings (env vars)
│   ├── sql_db.py              # dynamic data: hours, prices, availability
│   ├── vector_store.py        # Milvus/Chroma build + load helpers
│   ├── pdf_loader.py          # PDF page loading + merging
│   ├── semantic_chunker.py    # meaning-based chunking
│   ├── metadata_store.py      # chunk/document metadata DB (source of truth)
│   ├── reservation.py         # reservation slot-filling agent
│   ├── rag_chain.py           # intent classification + grounded answers
│   ├── chatbot.py             # orchestrator (ties everything together)
│   └── guardrails/pii_filter.py  # PII detection/redaction
├── admin_agent/
│   ├── agent.py               # admin approval agent; records approvals
│   ├── api.py                 # REST endpoints for requests and decisions
│   ├── cli.py                 # natural-language admin console
│   ├── notifier.py            # console/email/Slack/REST notifications
│   └── store.py               # SQLite-backed approval requests
├── mcp_server/
│   ├── server.py              # MCP stdio server and write_reservation tool
│   ├── api.py                 # API-key-protected, rate-limited FastAPI writer
│   ├── client.py              # recorder modes used by AdminAgent
│   └── reservation_writer.py  # validated, locked append to text file
├── data/
│   ├── pdfs/                  # knowledge base PDFs go here
│   ├── generate_sample_pdfs.py
│   └── ingest.py              # PDF -> chunks -> metadata DB -> vector DB
├── evaluation/
│   ├── generate_qa_from_pdfs.py  # auto-generates real test questions
│   └── evaluate.py               # Recall@K, Precision@K, latency, accuracy
├── tests/                     # pytest, fully offline, 2+ tests per module
├── terraform/                 # IaC: Milvus + app via Docker provider
├── docs/                      # presentation generator
├── .github/workflows/ci.yml   # CI: lint + test + docker build
├── docker-compose.yml         # local Milvus stack
├── Dockerfile
└── main.py                    # user-facing chatbot CLI
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

cp .env.example .env   # then edit .env and set OPENAI_API_KEY
```

Optional — start a real Milvus instance (otherwise the app automatically
falls back to a local Chroma store, no Docker required):

```bash
docker compose up -d
```

## Run

```bash
# 1. Create demo PDFs for the knowledge base (or drop your own files into data/pdfs/)
python -m data.generate_sample_pdfs

# 2. Ingest: PDF → semantic chunks → metadata DB → vector DB
python -m data.ingest

# 3. Chat
python main.py
```

After a reservation is escalated, an administrator can approve or refuse it
through the admin REST API or natural-language CLI:

```bash
# Admin REST API (port 8001)
uvicorn admin_agent.api:app --port 8001

# Or, with an OpenAI API key configured, use the admin CLI
python -m admin_agent.cli
```

With the default `MCP_CLIENT_MODE=inprocess`, approval appends the confirmed
reservation to `data/reservations/confirmed_reservations.txt`. To route writes
through the FastAPI writer instead, set `MCP_CLIENT_MODE=http` and
`MCP_HTTP_URL=http://localhost:8002`, then start the writer in another
terminal:

```bash
uvicorn mcp_server.api:app --host 127.0.0.1 --port 8002
```

The standalone MCP stdio server is available to MCP-compatible clients with
`python -m mcp_server.server`. See [mcp_server/README.md](mcp_server/README.md)
for recorder modes, API details, and focused tests.

Each approved reservation is appended as one line in the format
`Name | Car Number | Reservation Period | Approval Time`:

```text
Jane Doe | ABC123 | 2026-10-10 09:00 -> 2026-10-10 11:00 | 2026-10-07T09:05:00
```

Refused requests are not written to the confirmed-reservations file.

Verify ingestion worked:

```bash
python -c "
from src.metadata_store import list_documents, list_chunks
print(len(list_documents()), 'documents,', len(list_chunks()), 'chunks')
"
```

## Evaluate

```bash
# Auto-generate real test questions from the ingested PDFs
python -m evaluation.generate_qa_from_pdfs --per-chunk 2

# Run retrieval + answer-correctness evaluation against those questions
python -m evaluation.evaluate --grader llm
# -> evaluation/REPORT.md, evaluation/eval_results.json
```

`REPORT.md` contains Recall@K, Precision@K, retrieval latency (mean/P50/P95),
and LLM-judged answer accuracy with failed-case details — this is the
system performance evaluation report.

## Test

```bash
pytest -v   # fully offline, no API key required
```

## Docker

```bash
docker build -t parking-chatbot .
docker run --rm -it --env-file .env parking-chatbot
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR:
lint (flake8) → pytest with coverage (fully offline, no API key required) → Docker build.

## Infrastructure as Code

`terraform/` provisions Milvus (+ etcd/minio) and, optionally, the chatbot
app container via the Docker Terraform provider — see `terraform/README.md`.

```bash
cd terraform
terraform init
terraform apply -var="openai_api_key=sk-..." -var="deploy_app_container=true"
```

## Presentation

The generated deck covers the chatbot, admin approval workflow, and MCP
reservation file storage. Insert screenshots into the marked demo slides.

```bash
pip install -r docs/requirements-docs.txt
python -m docs.generate_presentation
# -> docs/Parking_Chatbot_Stage3.pptx
```

## Test coverage

Tests are designed to run offline (fake LLMs/embeddings, temporary SQLite
databases, and mocked collaborators — no network or API key required):

| Module | Tests |
|---|---|
| `src/config.py` | 2 |
| `src/sql_db.py` | 4 |
| `src/vector_store.py` | 3 |
| `src/pdf_loader.py` | 2 |
| `src/semantic_chunker.py` | 2 |
| `src/metadata_store.py` | 2 |
| `src/reservation.py` | 3 |
| `src/rag_chain.py` | 2 |
| `src/chatbot.py` | 4 |
| `src/guardrails/pii_filter.py` | 3 |
| `data/ingest.py` | 2 |
| `admin_agent/` and `mcp_server/` | see focused test modules below |

Run the Stage 3 approval and reservation-writer tests directly:

```bash
pytest tests/test_admin_agent.py tests/test_admin_api.py tests/test_reservation_writer.py tests/test_mcp_api.py tests/test_mcp_rate_limit.py tests/test_mcp_client.py tests/test_mcp_server_tool.py tests/test_mcp_config.py -v
```

## Design notes

- **PDF knowledge base**: `data/pdfs/*.pdf` → page-level load → merged
  full-document text → `SemanticChunker` splits on embedding-distance
  "meaning shifts" between sentences (not a fixed character window), with
  automatic fallback to `RecursiveCharacterTextSplitter` if unavailable or
  it errors at runtime.
- **Metadata DB**: every chunk and its parent document are persisted in
  SQLite (`data/metadata.db`) with file hash, page, chunk index, splitter
  used, and full text — auditable and queryable independently of the
  vector DB. The vector store is always rebuilt from this DB, so the two
  can't drift apart.
- **Resilience**: vector backend falls back Milvus → Chroma; PII filter
  falls back Presidio → regex; chunker falls back semantic → recursive.
  The bot degrades instead of crashing.
- **Guardrails**: inbound scan blocks unsafe pastes (credit card/SSN/IBAN)
  outside the reservation flow; outbound redaction is applied to
  RAG-generated answers as defense-in-depth, but not to the reservation
  summary (the user's own data being echoed back).
- **Confirmed reservation storage**: only administrator-approved requests
  are recorded. The shared writer validates fields, rejects pipe/newline
  injection, confines writes to the configured output directory, and uses
  a file lock plus `fsync` to protect concurrent and durable appends.
- **MCP/API security**: the FastAPI writer accepts `MCP_API_KEY` through
  the `x-api-key` header and applies per-client rate limiting. The admin
  API's mutating endpoints can be protected with `ADMIN_API_KEY`. Both keys
  are optional for local development, so configure them before exposing
  either API beyond a trusted local network. The writer never accepts a
  client-selected output path.
- **Evaluation**: test questions are generated by an LLM directly from
  real ingested chunks (`evaluation/generate_qa_from_pdfs.py`), so ground
  truth (relevant chunk id + reference answer) is guaranteed to exist in
  the knowledge base. `evaluation/evaluate.py` then reports Recall@K,
  Precision@K, retrieval latency, and LLM-judged answer accuracy.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pytest` fails before anything else | broken install | re-check `pip install -r requirements.txt`, confirm `en_core_web_sm` downloaded |
| `AuthenticationError` during ingest/chat | bad/missing `OPENAI_API_KEY` | check `.env` is loaded (run commands from repo root) |
| `FileNotFoundError: No PDFs found` | skipped PDF generation | run `python -m data.generate_sample_pdfs` |
| Bot answers "I don't know" to everything | ingestion didn't run / vector store empty | re-run `python -m data.ingest`, verify with the metadata DB check above |
| `[vector_store] Milvus unavailable...` always shows | Milvus not running | expected if you haven't run `docker compose up -d` — this is the designed fallback |

## Stages

- Stage 1: RAG chatbot and reservation-detail collection.
- Stage 2: `admin_agent/` — human-in-the-loop approval workflow.
- Stage 3: `mcp_server/` — records approved reservations to file.
- Future work: `graph/` — LangGraph orchestration, load/integration tests, and docs.