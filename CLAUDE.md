# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered cloud migration platform (**v4.2.0**) that orchestrates a **6-phase + 2 sub-phase** migration workflow using LangGraph + LangChain with **OCI Generative AI (Google Gemini Pro, default; Cohere Command R+ optional)**. Migrates workloads from AWS/Azure/GCP/On-Prem to Oracle Cloud Infrastructure (OCI).

## Commands

```bash
# Setup — use the conda env for all development and testing
conda activate claudecloudmigration

# Install dependencies if needed
pip install -r requirements.txt

# Run the evaluation harness (primary test suite)
python -m tests.evals.eval_harness                            # all 4 scenarios, all phases
python -m tests.evals.eval_harness --phase discovery          # discovery phase only (fast)
python -m tests.evals.eval_harness --scenario aws_eks_rds     # single scenario

# Legacy root-level integration scripts (still valid)
python test_workflow.py              # Basic Phase 1 smoke test
python test_complete_workflow.py     # Full 6-phase end-to-end test
```

> **Important:** Always run tests via `python -m tests.evals.eval_harness` (module invocation), not `python tests/evals/eval_harness.py` — the latter fails because `src.*` imports require the project root on `sys.path`.

The `tests/evals/` directory contains the evaluation harness. `tests/__init__.py` and `tests/evals/__init__.py` exist. Root-level test scripts (`test_workflow.py`, `test_complete_workflow.py`) are supplementary.

## Architecture

### Workflow Engine (LangGraph StateGraph)

The system executes a **6-phase + 2 sub-phase** migration pipeline defined in `src/agents/workflow.py`:

1. **Discovery** (`phase1_discovery.py`, 7 nodes) — Intake, KB enrichment, document ingestion, BOM analysis, evidence extraction, gap detection, clarification loop
2. **Phase 1.9 — Security Posture Config** (`phase1_discovery.py`, 1 node) — `security_posture_config`: detects compliance frameworks (CIS, HIPAA, PCI-DSS, SOC2, GDPR, ISO27001, FedRAMP) via keyword + LLM; populates `state.compliance_frameworks`
3. **Phase 1.10 — Dependency Analysis Config** (`phase1_discovery.py`, 1 node) — `dependency_analysis_config`: builds graph from discovered services, calls `DependencyAnalysisServer` to compute deployment waves; populates `state.dependency_analysis` and `state.applied_constraints`
4. **Analysis** (`phase2_analysis.py`, 7 nodes) — Current state reconstruction, service mapping (via `MappingServer`), ArchHub/LiveLabs discovery, sizing (`SizingServer`), cost estimation (`PricingServer`)
5. **Design** (`phase3_design.py`, 6 nodes) — Architecture modeling, component definition, dependency mapping, topological sort, diagram generation
6. **Review** (`phase4_review.py`, 6 nodes) — Validation, compliance, risk assessment, cost verification, approval loop (up to N iterations)
7. **Implementation** (`phase5_implementation.py`, 3 pathways + convergence) — Strategy selection → Pathway A (pre-packaged components), Pathway B (dynamic Terraform via `TerraformGenServer` + `TerraformValidatorServer`), or Pathway C (third-party frameworks) → `prepare_implementation_review`
8. **Deployment** (`phase6_deployment.py`, 10 nodes) — Pre-validation, OCI Resource Manager stack creation, Terraform plan/apply, monitoring, post-validation, report, **package deliverables** (Phase 6.5), **data lineage** (final)

**6 review gates** (`review_gates.py`) interrupt the workflow for human approval: `discovery_review_gate`, `archhub_review_gate`, `livelabs_review_gate`, `design_review_gate`, `code_review_gate`, `plan_review_gate`.

### Node Pattern

Every workflow node is a pure function: `MigrationState → MigrationState`. Nodes follow a consistent pattern:

```python
def my_node(state: MigrationState) -> MigrationState:
    t0 = time.time()
    log_node_entry(state.migration_id, "phase", "node_name", {...})
    try:
        # 1. Build LangChain LCEL chain: prompt | llm | JsonOutputParser
        llm = get_llm()
        chain = prompt | llm | JsonOutputParser()
        result = chain.invoke({...})
        log_llm_call(state.migration_id, "node_name", ...)
        # 2. Optionally call MCP server tools
        # 3. Update state fields
        log_node_exit(state.migration_id, "phase", "node_name", {...}, (time.time()-t0)*1000)
        return state
    except Exception as e:
        log_error(state.migration_id, "ErrorType", str(e), "phase")
        state.errors.append(f"error: {str(e)}")
        return state   # never raise — always return state
```

**Critical rule:** Nodes must never raise exceptions. All errors are appended to `state.errors` and the node returns the (partially updated) state.

### State Model

`src/models/state_schema.py` defines `MigrationState` (Pydantic BaseModel v4.2.0) — a single state object flowing through the entire workflow.

**Top-level fields on `MigrationState`:**

| Field | Type | Purpose |
|-------|------|---------|
| `migration_id`, `created_at`, `updated_at` | metadata | Identity |
| `current_phase`, `phase_status` | `str`, `PhaseStatus` | Workflow position |
| `user_context`, `source_provider`, `target_region` | `str` | Inputs |
| `uploaded_documents`, `bom_file` | `List[str]`, `Optional[str]` | Documents |
| `discovery` | `DiscoveryState` | Phase 1 output |
| `analysis` | `AnalysisState` | Phase 2 output |
| `design` | `DesignState` | Phase 3 output |
| `review` | `ReviewState` | Phase 4 output |
| `implementation` | `ImplementationState` | Phase 5 output |
| `deployment` | `DeploymentState` | Phase 6 output |
| `on_demand` | `OnDemandState` | Risk/cost/KB/health |
| `compliance_frameworks` | `List[str]` | **v4.2.0** Phase 1.9 output |
| `compliance_frameworks_status` | `str` | **v4.2.0** Phase 1.9 status |
| `dependency_constraints` | `Dict[str, Any]` | **v4.2.0** User-supplied wave constraints |
| `dependency_analysis` | `Dict[str, Any]` | **v4.2.0** Phase 1.10 wave plan |
| `dependency_analysis_status` | `str` | **v4.2.0** Phase 1.10 status |
| `applied_constraints` | `Dict[str, Any]` | **v4.2.0** Applied constraint summary |
| `deliverables_package` | `Dict[str, Any]` | **v4.2.0** Phase 6.5 bundle |
| `deliverables_package_status` | `str` | **v4.2.0** Phase 6.5 status |
| `data_lineage_report` | `Dict[str, Any]` | **v4.2.0** Provenance across 16 fields |
| `data_lineage_status` | `str` | **v4.2.0** Data lineage status |
| `*_review_decision`, `*_review_feedback` | `Optional[ReviewDecision]`, `str` | Gate decisions |
| `messages`, `errors` | `List[Dict]`, `List[str]` | Communication/audit |
| `risk_analysis_requested`, `cost_optimization_requested` | `bool` | Feature flags |

When adding new state fields, always add them at the `MigrationState` root level (not inside nested models) unless they are clearly scoped to one phase's output.

### LLM Layer (`src/utils/oci_genai.py` + `src/llm/`)

`get_llm()` returns one of two backends based on `OCI_GENAI_MODEL_TYPE` env var:
- **`"gemini"` (default)** — `GeminiLangChainWrapper` from `src/llm/gemini_wrapper.py` — Google Gemini Pro via OCI GenAI inference endpoint
- **`"cohere"`** — `OCIGenAI` from `src/utils/oci_genai.py` — Cohere Command R+ via OCI GenAI

All nodes call `get_llm()` at invocation time (not at import time) so the backend is resolved from config on each call.

### MCP Tool Servers (`src/mcp_servers/`)

**16 implemented servers** (not placeholders):

| Group | Servers |
|-------|---------|
| Knowledge & Docs | `kb_server`, `docs_server`, `xls_finops_server` |
| Service Mapping & Ref Arch | `mapping_server`, `refarch_server`, `oracle_archhub_server`, `oracle_livelabs_server` |
| Sizing & Pricing | `sizing_server`, `pricing_server` |
| IaC | `terraform_gen_server`, `terraform_validator_server`, `dependency_analysis_server` |
| Project Mgmt & Deployment | `deliverables_server`, `project_export_server`, `oci_rm_server`, `deployment_monitor_server` |

**`DependencyAnalysisServer` API** (important — takes a `graph` dict, not Terraform code):
```python
# Step 1: build graph from module list
graph_result = dependency_analysis_server.analyze_terraform_dependencies(
    modules=[{"name": "vcn", "type": "oci_core_vcn", "depends_on": []}]
)
graph = graph_result["graph"]   # {node_name: [dependency_names]}

# Step 2: compute waves / estimate / diagram
waves  = dependency_analysis_server.optimize_deployment_waves(graph=graph)
timing = dependency_analysis_server.calculate_deployment_estimate(graph=graph)
diag   = dependency_analysis_server.generate_dependency_diagram(graph=graph)
```

LangChain tool wrappers for all servers live in `src/tools/mcp_tools.py`.

### Key Utilities (`src/utils/`)

| Module | Purpose |
|--------|---------|
| `oci_genai.py` | LangChain LLM/embeddings wrappers (OCIGenAI + factory `get_llm()`) |
| `config.py` | Pydantic Settings — loads from env vars / `.env`; `config.app`, `config.oci`, `config.genai` |
| `checkpoint.py` | Oracle 23ai checkpoint saver (extends LangGraph `BaseCheckpointSaver`); falls back to in-memory |
| `document_processor.py` | Multi-format extraction: PDF, DOCX, Excel BOM |
| `logger.py` | JSON-structured logging; helpers: `log_node_entry`, `log_node_exit`, `log_llm_call`, `log_mcp_call`, `log_error` |

### Evaluation Harness (`tests/evals/`)

```
tests/evals/
├── eval_harness.py          # EvaluationHarness — orchestrates scenarios × phases
├── accuracy_metrics.py      # InvariantChecker (safe eval) + AccuracyMetrics
└── scenarios/
    ├── __init__.py           # ALL_SCENARIOS registry (4 scenarios)
    ├── aws_eks_rds_scenario.py        # 10 invariants — EKS+RDS, hipaa+pci_dss
    ├── aws_webapp_scenario.py         # 8 invariants — 3-tier web, soc2
    ├── azure_vm_sql_scenario.py       # 8 invariants — Azure VM+SQL, iso27001
    └── security_compliance_scenario.py # 15 invariants — force_sequential, 5 frameworks (v4.2.0)
```

Each scenario exposes `SCENARIO_ID`, `INPUT` (dict → `MigrationState` kwargs), and `INVARIANTS` (list of `{id, description, phase, field, check}` dicts). `check` is a Python expression over `value` (the resolved field).

## Environment Variables

Key configuration (see `src/utils/config.py` for the full Pydantic schema):

**OCI Auth:**
- `OCI_REGION`, `OCI_TENANCY_ID`, `OCI_USER_ID`, `OCI_FINGERPRINT`, `OCI_PRIVATE_KEY_PATH`, `OCI_COMPARTMENT_ID`

**GenAI / LLM:**
- `OCI_GENAI_ENDPOINT` — inference endpoint URL
- `OCI_GENAI_MODEL_ID` — model OCID (Gemini or Cohere)
- `OCI_GENAI_MODEL_TYPE` — `"gemini"` (default) or `"cohere"`

**Oracle 23ai (checkpoint):**
- `ORACLE_DB_HOST`, `ORACLE_DB_PORT`, `ORACLE_DB_SERVICE`, `ORACLE_DB_USER`, `ORACLE_DB_PASSWORD`
- Falls back to in-memory checkpoint store when DB is unreachable.

**Workflow thresholds:**
- `DISCOVERY_CONFIDENCE_THRESHOLD` (default `0.80`) — triggers clarification loop in Phase 1
- `REVIEW_APPROVAL_THRESHOLD` (default `0.90`) — Phase 4 approval loop gate

**App:**
- `EXPORT_DIR` (default `./exports`) — where Terraform ZIPs and deliverables are written
- `APP_VERSION` (default `4.0.0`) — overrideable for release tagging

## Development Rules & Recommendations

### Adding a new workflow node

1. Implement the node function in the appropriate `src/agents/phaseN_*.py` file following the node pattern above.
2. Add any new state fields to `MigrationState` in `src/models/state_schema.py` — at the root level with a `status` companion field (`str = "pending"`).
3. Import the function in `src/agents/workflow.py`, add it with `workflow.add_node(...)`, and wire edges. Each node can have **only one unconditional outgoing edge** — use `add_conditional_edges` for branching.
4. Add invariants for the new node to the relevant eval scenario in `tests/evals/scenarios/`.
5. Test: `conda run -n claudecloudmigration python -m tests.evals.eval_harness --phase <phase>`.

### Adding a new MCP server

1. Create `src/mcp_servers/<name>_server.py` with a class following the existing server pattern (constructor, `_record(latency, success)`, tool methods returning `Dict[str, Any]`).
2. Export both the class and a singleton instance from the module (e.g. `<name>_server = NameServer()`).
3. Register the class in `src/mcp_servers/__init__.py` (import + `__all__`).
4. Add LangChain tool wrapper(s) in `src/tools/mcp_tools.py`.

### Workflow graph rules

- `workflow.compile(interrupt_before=[...])` lists **review gate node names** only — do not add non-gate nodes.
- Never add two `add_edge(source, X)` calls for the same `source` — the second silently overrides the first. Use `add_conditional_edges` instead.
- The `prepare_implementation_review` node is a **convergence point** for all three implementation pathways (A/B/C). Its only outgoing edge is → `pre_deployment_validation`. Do not bypass it.

### Logging conventions

Use the helpers from `src/utils/logger.py` consistently:
- `log_node_entry(migration_id, phase, node, inputs_dict)` — call at the very start of every node
- `log_node_exit(migration_id, phase, node, outputs_dict, duration_ms)` — call just before `return state`
- `log_llm_call(migration_id, node, prompt_preview, response_preview, duration_ms)` — after every LLM invoke
- `log_mcp_call(migration_id, server, tool, inputs, result, duration_ms)` — after every MCP server call
- `log_error(migration_id, error_type, message, phase)` — in every `except` block

### State field conventions

- Phase-output dicts (e.g. `dependency_analysis`, `deliverables_package`, `data_lineage_report`) always have a companion `*_status: str` field defaulting to `"pending"`. Set it to `"completed"` on success or `"failed"` on error.
- Never store large binary blobs in state — store file paths instead.
- Compliance frameworks are always lowercase strings from the set: `cis, hipaa, pci_dss, soc2, gdpr, iso27001, fedramp`.
