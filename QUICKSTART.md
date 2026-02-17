# Cloud Migration Agent Platform v4.0.0 — Quick Start

AI-powered migration from AWS / Azure / GCP / On-Premises to Oracle Cloud Infrastructure (OCI).

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10 – 3.13 |
| OCI account | with GenAI Service enabled |
| (Optional) Oracle 23ai | for checkpointing / vector search |

---

## 1. Clone and set up the environment

```bash
git clone https://github.com/krishna1803/cloud-migration-agent.git
cd cloud-migration-agent

python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

---

## 2. Configure environment variables

Copy the example below to a `.env` file in the project root and fill in your OCI credentials:

```dotenv
# ── OCI Authentication ──────────────────────────────────────────
OCI_REGION=us-ashburn-1
OCI_TENANCY_ID=ocid1.tenancy.oc1..your-tenancy-id
OCI_USER_ID=ocid1.user.oc1..your-user-id
OCI_FINGERPRINT=aa:bb:cc:...your-fingerprint
OCI_PRIVATE_KEY_PATH=~/.oci/oci_api_key.pem
OCI_COMPARTMENT_ID=ocid1.compartment.oc1..your-compartment-id

# ── OCI Generative AI ────────────────────────────────────────────
OCI_GENAI_ENDPOINT=https://inference.generativeai.us-chicago-1.oci.oraclecloud.com
OCI_GENAI_MODEL_ID=cohere.command-r-plus
OCI_GENAI_EMBEDDING_MODEL_ID=cohere.embed-english-v3.0
OCI_GENAI_MAX_TOKENS=4096
OCI_GENAI_TEMPERATURE=0.1

# ── Oracle 23ai (optional — for checkpointing & vector search) ──
# Leave blank to disable; the platform falls back to in-memory storage.
ORACLE_DB_HOST=localhost
ORACLE_DB_PORT=1521
ORACLE_DB_SERVICE=FREEPDB1
ORACLE_DB_USER=
ORACLE_DB_PASSWORD=

# ── Application (all optional — these are the defaults) ─────────
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
UI_HOST=0.0.0.0
UI_PORT=7860
UPLOAD_DIR=./uploads
EXPORT_DIR=./exports
CHECKPOINT_DIR=./checkpoints
DISCOVERY_CONFIDENCE_THRESHOLD=0.80
REVIEW_APPROVAL_THRESHOLD=0.90
```

---

## 3. Run the platform

### Option A — API + UI together (recommended)

```bash
python main.py both
```

This starts:
- **REST API** on `http://localhost:8000`
- **Gradio UI** on `http://localhost:7860`

Open `http://localhost:7860` in your browser to use the UI.

---

### Option B — API only

```bash
python main.py api
```

Interactive API docs are available at `http://localhost:8000/docs`.

---

### Option C — UI only (expects API already running)

```bash
python main.py ui
```

---

### Custom ports / hot-reload (development)

```bash
python main.py both --api-port 8080 --ui-port 7861
python main.py api  --reload          # hot-reload on code changes
```

---

## 4. Connect the UI to the API

The Gradio UI talks to the REST API at `http://localhost:8000` by default.
If you change the API port, update `API_BASE` in [src/ui/app.py](src/ui/app.py#L16):

```python
API_BASE = "http://localhost:8080"   # match your --api-port
```

To make it configurable without editing code, set an environment variable and
restart:

```bash
export API_BASE_URL=http://your-api-host:8080
```

*(The UI currently hard-codes the URL; exposing it as an env var is a one-line
change in `src/ui/app.py` if needed.)*

---

## 5. Verify everything is working

```bash
# Health check
curl http://localhost:8000/health

# MCP server monitor
curl http://localhost:8000/health/mcp-monitor

# Run the test suite (no OCI credentials needed)
python test_new_components.py
```

Expected test output:
```
Ran 38 tests in ~2s
OK
```

---

## 6. Run your first migration

### Via the Gradio UI

1. Open `http://localhost:7860`
2. Go to the **Phase 1 — Discovery** tab
3. Fill in **Migration Context** (describe the workload), **Source Provider** (AWS / Azure / GCP / On-Prem), and **Target Region**
4. Click **Start Migration** — the platform returns a `migration_id`
5. Progress through each phase tab, approving review gates as you go

### Via the REST API

```bash
# Start a migration
curl -X POST http://localhost:8000/migrations \
  -H "Content-Type: application/json" \
  -d '{
    "user_context": "Migrate a 3-tier e-commerce app running on AWS EC2, RDS MySQL, and S3",
    "source_provider": "AWS",
    "target_region": "us-ashburn-1"
  }'

# The response contains a migration_id, e.g. "mig-abc123"

# Poll status
curl http://localhost:8000/migrations/mig-abc123

# Approve a review gate
curl -X POST http://localhost:8000/migrations/mig-abc123/discovery-review \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve", "feedback": "Looks good"}'
```

---

## 7. Project structure

```
cloud-migration-agent/
├── main.py                      # Entry point (api / ui / both)
├── requirements.txt
├── .env                         # Your credentials (not committed)
├── src/
│   ├── agents/                  # LangGraph workflow nodes (6 phases)
│   │   ├── workflow.py          # StateGraph definition + compile
│   │   ├── phase1_discovery.py
│   │   ├── phase2_analysis.py
│   │   ├── phase3_design.py
│   │   ├── phase4_review.py
│   │   ├── phase5_implementation.py
│   │   ├── phase6_deployment.py
│   │   └── review_gates.py      # 10 human-in-the-loop checkpoints
│   ├── api/
│   │   └── routes.py            # 30 FastAPI endpoints
│   ├── ui/
│   │   └── app.py               # 13-tab Gradio interface
│   ├── mcp_servers/             # 10 MCP tool servers
│   ├── knowledge_base/          # RAG knowledge base (Oracle 23ai / in-memory)
│   ├── models/
│   │   └── state_schema.py      # MigrationState (Pydantic)
│   └── utils/
│       ├── config.py            # Pydantic-settings config
│       ├── oci_genai.py         # OCI Cohere Command R+ LangChain wrapper
│       ├── checkpoint.py        # Oracle 23ai checkpoint saver
│       └── logger.py            # JSON-structured logging
└── test_new_components.py       # 38 unit tests (dependency-free)
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'gradio'` | `pip install gradio requests` |
| UI shows "Connection error" | Ensure `python main.py api` is running first |
| `OCI SDK auth error` | Check `.env` credentials and that your OCI key file exists |
| `TypeError: expected str … FieldInfo` | Pydantic-settings mismatch — run `pip install pydantic-settings==2.5.2` |
| Tests fail | Run `python test_new_components.py` — no OCI credentials needed |
