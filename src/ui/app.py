"""
Gradio UI for the Cloud Migration Agent Platform v4.0.0.
13-tab interface covering the complete 6-phase migration workflow.
"""

import json
from typing import Any, Tuple

try:
    import gradio as gr
    import requests
    GRADIO_AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as _e:
    GRADIO_AVAILABLE = False
    _IMPORT_ERROR = _e

try:
    from src.utils.config import config as _cfg
    API_BASE = f"http://localhost:{_cfg.api.port}"
except Exception:
    API_BASE = "http://localhost:8000"


def _post(endpoint: str, data: dict = None, params: dict = None) -> Tuple[bool, Any]:
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data or {}, params=params or {}, timeout=30)
        return r.ok, r.json() if r.ok else {"error": r.text[:200]}
    except Exception as e:
        return False, {"error": str(e)}


def _get(endpoint: str, params: dict = None) -> Tuple[bool, Any]:
    try:
        r = requests.get(f"{API_BASE}{endpoint}", params=params or {}, timeout=30)
        return r.ok, r.json() if r.ok else {"error": r.text[:200]}
    except Exception as e:
        return False, {"error": str(e)}


def create_ui():
    """Create and return the Gradio UI application."""
    if not GRADIO_AVAILABLE:
        raise ImportError(
            f"Failed to import UI dependencies: {_IMPORT_ERROR}. "
            "Install with: pip install gradio requests"
        ) from _IMPORT_ERROR

    with gr.Blocks(title="Cloud Migration Agent v4.0.0") as app:

        gr.HTML("""<div style="background:linear-gradient(135deg,#C74634,#F80000);color:white;padding:20px;border-radius:8px;margin-bottom:20px;">
            <h1>Cloud Migration Agent Platform v4.0.0</h1>
            <p>AI-powered migration from AWS/Azure/GCP/On-Premises to Oracle Cloud Infrastructure</p></div>""")

        migration_id = gr.State("")

        with gr.Tabs():

            # Tab 1: Discovery
            with gr.Tab("Phase 1: Discovery"):
                gr.Markdown("## Start Migration")
                with gr.Row():
                    with gr.Column():
                        ctx = gr.Textbox(label="Migration Context", placeholder="Describe your current architecture...", lines=5)
                        provider = gr.Dropdown(["AWS", "Azure", "GCP", "On-Premises"], value="AWS", label="Source Provider")
                        region = gr.Dropdown(["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1", "ap-tokyo-1"], value="us-ashburn-1", label="Target OCI Region")
                    with gr.Column():
                        start_out = gr.JSON(label="Response")
                        mid_display = gr.Textbox(label="Migration ID", interactive=False)
                start_btn = gr.Button("Start Migration", variant="primary", size="lg")

                def start_migration(c, p, r):
                    ok, result = _post("/migrations", {"user_context": c, "source_provider": p, "target_region": r})
                    mid = result.get("migration_id", "") if ok else ""
                    return result, mid, mid

                start_btn.click(start_migration, [ctx, provider, region], [start_out, migration_id, mid_display])

                gr.Markdown("### Submit Clarifications")
                clarif = gr.Textbox(label='Clarifications (JSON)', placeholder='{"vpc_count": "3 VPCs"}', lines=2)
                clarif_btn = gr.Button("Submit Clarifications")
                clarif_out = gr.JSON(label="Response")

                def sub_clarif(mid, cj):
                    if not mid: return {"error": "No active migration"}
                    try: c = json.loads(cj) if cj else {}
                    except: return {"error": "Invalid JSON"}
                    ok, r = _post(f"/migrations/{mid}/clarifications", {"clarifications": c})
                    return r

                clarif_btn.click(sub_clarif, [migration_id, clarif], clarif_out)

            # Tab 2: Discovery Review
            with gr.Tab("Phase 1.5: Discovery Review"):
                gr.Markdown("## Review Discovered Architecture")
                fetch_btn = gr.Button("Fetch Migration Status")
                status_out = gr.JSON(label="Status")
                fetch_btn.click(lambda mid: _get(f"/migrations/{mid}")[1] if mid else {"error": "No migration"}, [migration_id], status_out)

                disc_dec = gr.Radio(["approve", "request_changes", "reject"], value="approve", label="Decision")
                disc_fb = gr.Textbox(label="Feedback", lines=2)
                disc_btn = gr.Button("Submit Discovery Review", variant="primary")
                disc_out = gr.JSON(label="Response")

                def sub_disc(mid, d, fb):
                    if not mid: return {"error": "No migration"}
                    ok, r = _post(f"/migrations/{mid}/discovery-review", {"decision": d, "feedback": fb})
                    return r

                disc_btn.click(sub_disc, [migration_id, disc_dec, disc_fb], disc_out)

            # Tab 3: Analysis
            with gr.Tab("Phase 2: Analysis"):
                gr.Markdown("## OCI Architecture Analysis")
                fetch_analysis = gr.Button("Fetch Analysis")
                analysis_out = gr.JSON(label="Analysis")
                fetch_analysis.click(lambda mid: _get(f"/migrations/{mid}/phase/analysis")[1] if mid else {"error": "No migration"}, [migration_id], analysis_out)

                gr.Markdown("### ArchHub Review")
                arch_dec = gr.Radio(["approve", "request_changes"], value="approve", label="ArchHub Decision")
                arch_btn = gr.Button("Submit ArchHub Review")
                arch_out = gr.JSON(label="Response")
                arch_btn.click(lambda mid, d: _post(f"/migrations/{mid}/archhub-review", {"decision": d})[1] if mid else {"error": "No migration"}, [migration_id, arch_dec], arch_out)

                gr.Markdown("### LiveLabs Review")
                ll_dec = gr.Radio(["approve", "request_changes"], value="approve", label="LiveLabs Decision")
                ll_btn = gr.Button("Submit LiveLabs Review")
                ll_out = gr.JSON(label="Response")
                ll_btn.click(lambda mid, d: _post(f"/migrations/{mid}/livelabs-review", {"decision": d})[1] if mid else {"error": "No migration"}, [migration_id, ll_dec], ll_out)

            # Tab 4: Design
            with gr.Tab("Phase 3: Design"):
                gr.Markdown("## Formal Architecture Design")
                fetch_design = gr.Button("Fetch Design")
                design_out = gr.JSON(label="Design")
                fetch_design.click(lambda mid: _get(f"/migrations/{mid}/phase/design")[1] if mid else {"error": "No migration"}, [migration_id], design_out)

                design_dec = gr.Radio(["approve", "request_changes", "reject"], value="approve", label="Design Decision")
                design_fb = gr.Textbox(label="Feedback", lines=2)
                design_btn = gr.Button("Submit Design Review", variant="primary")
                design_btn_out = gr.JSON(label="Response")
                design_btn.click(lambda mid, d, fb: _post(f"/migrations/{mid}/design-review", {"decision": d, "feedback": fb})[1] if mid else {"error": "No migration"}, [migration_id, design_dec, design_fb], design_btn_out)

            # Tab 5: Review
            with gr.Tab("Phase 4: Review"):
                gr.Markdown("## Final Validation & Approval")
                rev_dec = gr.Radio(["approve", "request_changes", "reject"], value="approve", label="Final Decision")
                rev_fb = gr.Textbox(label="Comments", lines=3)
                rev_btn = gr.Button("Submit Final Review", variant="primary")
                rev_out = gr.JSON(label="Response")
                rev_btn.click(lambda mid, d, fb: _post(f"/migrations/{mid}/review", {"decision": d, "feedback": fb})[1] if mid else {"error": "No migration"}, [migration_id, rev_dec, rev_fb], rev_out)

            # Tab 6: Implementation
            with gr.Tab("Phase 5: Implementation"):
                gr.Markdown("## Terraform Code Generation")
                with gr.Row():
                    gen_btn = gr.Button("Generate Terraform", variant="primary")
                    val_btn = gr.Button("Validate Code")
                    exp_btn = gr.Button("Export Project")
                tf_code = gr.Code(label="Generated Terraform", language="javascript", lines=15)
                tf_json = gr.JSON(label="Response")

                def gen_tf(mid):
                    if not mid: return "", {"error": "No migration"}
                    ok, r = _post("/terraform/generate", {"migration_id": mid})
                    code = "\n\n".join([f"# === {k} ===\n{v}" for k, v in r.get("files", {}).items()])
                    return code, r

                gen_btn.click(gen_tf, [migration_id], [tf_code, tf_json])
                val_out = gr.JSON(label="Validation")
                val_btn.click(lambda code: _post("/terraform/validate", {"terraform_code": code})[1], [tf_code], val_out)
                exp_out = gr.JSON(label="Export Response")
                exp_btn.click(lambda mid: _post("/projects/export", params={"migration_id": mid})[1] if mid else {"error": "No migration"}, [migration_id], exp_out)

            # Tab 7: Deployment
            with gr.Tab("Phase 6: Deployment"):
                gr.Markdown("## Deploy to Oracle Cloud Infrastructure")
                with gr.Row():
                    pre_btn = gr.Button("Pre-Deploy Validation")
                    stack_btn = gr.Button("Create OCI Stack")
                    deploy_btn = gr.Button("Deploy", variant="primary")
                    post_btn = gr.Button("Post-Deploy Validation")
                deploy_out = gr.JSON(label="Deployment Status")
                pre_btn.click(lambda mid: _post("/deployment/validate/pre", params={"migration_id": mid})[1] if mid else {"error": "No migration"}, [migration_id], deploy_out)
                stack_btn.click(lambda mid: _post("/oci/stacks/create", {"migration_id": mid, "stack_name": f"migration-{mid[:8]}", "compartment_id": "ocid1.compartment.oc1..example"})[1] if mid else {"error": "No migration"}, [migration_id], deploy_out)
                deploy_btn.click(lambda mid: _post("/deployment/report", params={"migration_id": mid})[1] if mid else {"error": "No migration"}, [migration_id], deploy_out)
                post_btn.click(lambda mid: _post("/deployment/validate/post", params={"migration_id": mid})[1] if mid else {"error": "No migration"}, [migration_id], deploy_out)

            # Tab 8: Risk Analysis
            with gr.Tab("Risk Analysis"):
                gr.Markdown("## Migration Risk Assessment")
                risk_btn = gr.Button("Analyze Risks", variant="primary")
                risk_out = gr.JSON(label="Risk Analysis")
                risk_btn.click(lambda mid: _get(f"/migrations/{mid}/risk-analysis")[1] if mid else {"error": "No migration"}, [migration_id], risk_out)

            # Tab 9: Cost Optimization
            with gr.Tab("Cost Optimization"):
                gr.Markdown("## Cost Savings Recommendations")
                cost_btn = gr.Button("Get Cost Recommendations", variant="primary")
                cost_out = gr.JSON(label="Recommendations")
                cost_btn.click(lambda mid: _get(f"/migrations/{mid}/cost-optimization")[1] if mid else {"error": "No migration"}, [migration_id], cost_out)

            # Tab 10: Knowledge Base
            with gr.Tab("Knowledge Base (RAG)"):
                gr.Markdown("## Semantic Search & LLM Q&A")
                kb_q = gr.Textbox(label="Question", placeholder="What is the OCI equivalent of AWS S3?", lines=2)
                kb_col = gr.Dropdown(["all", "service_mappings", "best_practices", "architecture_patterns", "pricing_info", "compliance_standards"], value="all", label="Collection")
                kb_btn = gr.Button("Search", variant="primary")
                kb_ans = gr.Textbox(label="AI Answer", lines=4, interactive=False)
                kb_docs = gr.JSON(label="Retrieved Documents")
                def q_kb(q, col):
                    ok, r = _post("/kb/query", {"query": q, "collection": col, "top_k": 5})
                    return (r.get("answer", ""), r.get("retrieved_documents", [])) if ok else (r.get("error", "Error"), [])
                kb_btn.click(q_kb, [kb_q, kb_col], [kb_ans, kb_docs])

            # Tab 11: MCP Health
            with gr.Tab("MCP Health Monitor"):
                gr.Markdown("## MCP Tool Health Dashboard")
                health_btn = gr.Button("Check MCP Health", variant="primary")
                health_out = gr.JSON(label="Health Status")
                health_btn.click(lambda: _get("/health/mcp-monitor")[1], [], health_out)

            # Tab 12: Status & Monitoring
            with gr.Tab("Status & Monitoring"):
                gr.Markdown("## Overall Migration Status")
                with gr.Row():
                    override_mid = gr.Textbox(label="Migration ID (optional)", placeholder="Use active or enter ID")
                    refresh_btn = gr.Button("Refresh Status")
                all_btn = gr.Button("List All Migrations")
                all_out = gr.JSON(label="All Migrations")
                status_detail = gr.JSON(label="Status Details")
                refresh_btn.click(lambda mid, ov: _get(f"/migrations/{ov.strip() or mid}")[1] if (ov.strip() or mid) else {"error": "No migration"}, [migration_id, override_mid], status_detail)
                all_btn.click(lambda: _get("/migrations")[1], [], all_out)

            # Tab 13: API Reference
            with gr.Tab("API Reference"):
                gr.Markdown("""
## API Reference

**Base URL:** `http://localhost:8000`
**Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
**ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/migrations` | Start new migration |
| GET | `/migrations/{id}` | Get migration status |
| POST | `/migrations/{id}/discovery-review` | Discovery review |
| GET | `/migrations/{id}/phase/analysis` | Analysis details |
| POST | `/migrations/{id}/archhub-review` | ArchHub review |
| POST | `/migrations/{id}/livelabs-review` | LiveLabs review |
| GET | `/migrations/{id}/phase/design` | Design details |
| POST | `/migrations/{id}/design-review` | Design review |
| POST | `/migrations/{id}/review` | Final review |
| POST | `/terraform/generate` | Generate Terraform |
| POST | `/terraform/validate` | Validate Terraform |
| POST | `/oci/stacks/create` | Create OCI RM stack |
| GET | `/migrations/{id}/risk-analysis` | Risk analysis |
| GET | `/migrations/{id}/cost-optimization` | Cost optimization |
| POST | `/kb/query` | Knowledge Base RAG |
| GET | `/health/mcp-monitor` | MCP health |
| GET | `/health` | Platform health |
""")

    return app


if __name__ == "__main__":
    ui = create_ui()
    ui.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft(primary_hue="orange"))
