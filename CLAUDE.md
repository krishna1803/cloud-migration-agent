# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered cloud migration platform (v4.0.0) that orchestrates 6-phase migration workflows using LangGraph + LangChain with OCI Generative AI (Cohere Command R+). Migrates workloads from AWS/Azure/GCP/On-Prem to Oracle Cloud Infrastructure (OCI).

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run tests (no pytest; tests are standalone scripts)
python test_workflow.py              # Basic Phase 1 test
python test_complete_workflow.py     # Full 6-phase end-to-end test
```

There is no Makefile, pyproject.toml, or lint configuration. The `tests/` directory exists but is empty; all tests live at the project root.

## Architecture

### Workflow Engine (LangGraph StateGraph)

The system executes a 6-phase migration pipeline defined in `src/agents/workflow.py`:

1. **Discovery** (`phase1_discovery.py`, 7 nodes) — Intake, document ingestion, BOM analysis, evidence extraction, gap detection
2. **Analysis** (`phase2_analysis.py`, 7 nodes) — Current state reconstruction, service mapping, ArchHub/LiveLabs discovery, sizing, cost estimation
3. **Design** (`phase3_design.py`, 6 nodes) — Architecture modeling, component definition, dependency mapping, topological sort, diagram generation
4. **Review** (`phase4_review.py`, 6 nodes) — Validation, compliance, risk assessment, cost verification, approval loop
5. **Implementation** (`phase5_implementation.py`, 5 nodes) — Strategy selection, Terraform module definition, code generation, validation, export
6. **Deployment** (`phase6_deployment.py`, 8 nodes) — Pre-validation, OCI Resource Manager stack creation, Terraform plan/apply, monitoring, reporting

**10 review gates** (`review_gates.py`) provide human-in-the-loop checkpoints between phases.

### Node Pattern

Every workflow node is a pure function: `MigrationState → MigrationState`. Nodes follow a consistent pattern:
- Log entry, update phase status
- Build a LangChain LCEL chain (`prompt | llm | JsonOutputParser`)
- Invoke `get_llm()` (returns `OCIGenAI` wrapper from `src/utils/oci_genai.py`)
- Update state fields, handle errors by appending to `state.errors`

### State Model

`src/models/state_schema.py` defines `MigrationState` (Pydantic BaseModel) — a single state object that flows through the entire workflow. It contains phase-specific nested models (`DiscoveryState`, `AnalysisState`, etc.) plus review gate decisions.

### Key Utilities (`src/utils/`)

| Module | Purpose |
|--------|---------|
| `oci_genai.py` | Custom LangChain LLM wrapper for OCI Cohere Command R+ |
| `config.py` | Pydantic Settings config loaded from env vars / `.env` |
| `checkpoint.py` | Oracle 23ai checkpoint saver (extends LangGraph `BaseCheckpointSaver`) |
| `document_processor.py` | Multi-format document extraction (PDF, DOCX, Excel BOM) |
| `logger.py` | JSON-structured logging with OpenTelemetry correlation |

### Not Yet Implemented

`src/api/`, `src/ui/`, `src/knowledge_base/`, `src/mcp_servers/`, and `src/tools/` are placeholder directories.

## Environment Variables

Key configuration (see `src/utils/config.py` for full schema):

- `OCI_REGION`, `OCI_TENANCY_ID`, `OCI_USER_ID`, `OCI_FINGERPRINT`, `OCI_PRIVATE_KEY_PATH`, `OCI_COMPARTMENT_ID` — OCI auth
- `OCI_GENAI_ENDPOINT`, `OCI_GENAI_MODEL_ID` — GenAI service
- `ORACLE_DB_HOST`, `ORACLE_DB_PORT`, `ORACLE_DB_SERVICE`, `ORACLE_DB_USER`, `ORACLE_DB_PASSWORD` — Oracle 23ai
- `DISCOVERY_CONFIDENCE_THRESHOLD` (0.80), `REVIEW_APPROVAL_THRESHOLD` (0.90) — workflow thresholds
