"""
Tests for newly implemented components (v4.0.0 gap fills).

Tests that can run without OCI SDK or full dependency set:
- MCP Tool Servers (10 servers)
- Knowledge Base (Oracle 23ai manager)
- FastAPI Routes structure
- Phase 5 routing logic (with mocked OCI)
- State schema
- main.py app creation
"""

import sys
import json
import types
import importlib.machinery
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, '.')

# --------------- Mock heavy dependencies before any imports ---------------
def _make_package_mock(name):
    """Create a mock module with proper Python module attributes.

    Uses types.ModuleType so that __spec__ is a real ModuleSpec object,
    satisfying Python 3.13 frozen importlib checks during 'from X import Y'.
    Attribute access on the module returns a new MagicMock via __getattr__.
    """
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=True)
    mod.__path__ = []
    mod.__package__ = name
    mod.__name__ = name
    # Allow any attribute access (returns MagicMock for undefined attrs)
    mod.__getattr__ = lambda attr: MagicMock()
    return mod

# OCI SDK
for mod in ['oci', 'oci.config', 'oci.generative_ai_inference',
            'oci.generative_ai_inference.models', 'oci.auth', 'oci.auth.signers']:
    sys.modules[mod] = _make_package_mock(mod)

# LangChain / LangGraph - need package mocks for sub-module access
for mod in ['langchain_core', 'langchain_core.language_models',
            'langchain_core.language_models.llms', 'langchain_core.prompts',
            'langchain_core.output_parsers', 'langchain_core.callbacks',
            'langchain_core.callbacks.manager', 'langchain_core.messages',
            'langchain_core.outputs', 'langchain_core.embeddings',
            'langgraph', 'langgraph.graph', 'langgraph.checkpoint',
            'langgraph.checkpoint.base', 'langchain', 'langchain_community',
            'networkx', 'chromadb', 'faiss']:
    sys.modules[mod] = _make_package_mock(mod)

# Document processing
for mod in ['pypdf', 'docx', 'openpyxl', 'pandas', 'PIL', 'PIL.Image']:
    sys.modules[mod] = _make_package_mock(mod)

# opentelemetry
for mod in ['opentelemetry', 'opentelemetry.trace', 'opentelemetry.sdk',
            'opentelemetry.sdk.trace', 'opentelemetry.exporter',
            'opentelemetry.exporter.otlp']:
    sys.modules[mod] = _make_package_mock(mod)

# pydantic-settings (used by config.py)
for mod in ['pydantic_settings']:
    sys.modules[mod] = _make_package_mock(mod)
# Provide BaseSettings as a real class so config.py can subclass it
_pydantic_settings_mod = sys.modules['pydantic_settings']
_pydantic_settings_mod.BaseSettings = type('BaseSettings', (), {
    '__init_subclass__': classmethod(lambda cls, **kw: None),
    'model_config': {},
})

# Pre-inject a fully mocked src.utils.config so Config() is never called.
# This prevents os.makedirs() from running with FieldInfo objects.
_mock_config_obj = MagicMock()
_mock_config_obj.oci.region = "us-ashburn-1"
_mock_config_obj.oci.compartment_id = ""
_mock_config_obj.genai.model_id = "cohere.command-r-plus"
_mock_config_obj.genai.max_tokens = 4096
_mock_config_obj.genai.temperature = 0.1
_mock_config_obj.genai.endpoint = "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"
_mock_config_obj.app.upload_dir = "/tmp/uploads"
_mock_config_obj.app.export_dir = "/tmp/exports"
_mock_config_obj.app.checkpoint_dir = "/tmp/checkpoints"
_mock_config_obj.api.host = "0.0.0.0"
_mock_config_obj.api.port = 8000

_src_utils_config_mod = types.ModuleType('src.utils.config')
_src_utils_config_mod.__spec__ = importlib.machinery.ModuleSpec('src.utils.config', None)
_src_utils_config_mod.config = _mock_config_obj
_src_utils_config_mod.Config = MagicMock(return_value=_mock_config_obj)
sys.modules['src.utils.config'] = _src_utils_config_mod

# Pre-inject src.utils.logger so logger is not instantiated from config
_src_utils_logger_mod = types.ModuleType('src.utils.logger')
_src_utils_logger_mod.__spec__ = importlib.machinery.ModuleSpec('src.utils.logger', None)
_src_utils_logger_mod.logger = MagicMock()
_src_utils_logger_mod.setup_logger = MagicMock()
_src_utils_logger_mod.log_review_gate = MagicMock()
_src_utils_logger_mod.log_phase_start = MagicMock()
_src_utils_logger_mod.log_phase_end = MagicMock()
_src_utils_logger_mod.log_agent_action = MagicMock()
sys.modules['src.utils.logger'] = _src_utils_logger_mod

# Pre-inject src.utils.oci_genai so OCI SDK is never imported
_src_utils_oci_mod = types.ModuleType('src.utils.oci_genai')
_src_utils_oci_mod.__spec__ = importlib.machinery.ModuleSpec('src.utils.oci_genai', None)
_src_utils_oci_mod.get_llm = MagicMock()
_src_utils_oci_mod.get_embeddings = MagicMock()
_src_utils_oci_mod.OCIGenAI = MagicMock()
_src_utils_oci_mod.OCIGenAIEmbeddings = MagicMock()
sys.modules['src.utils.oci_genai'] = _src_utils_oci_mod

# Pre-inject src.utils.checkpoint
_src_utils_ckpt_mod = types.ModuleType('src.utils.checkpoint')
_src_utils_ckpt_mod.__spec__ = importlib.machinery.ModuleSpec('src.utils.checkpoint', None)
_src_utils_ckpt_mod.checkpoint_saver = MagicMock()
_src_utils_ckpt_mod.OracleCheckpointSaver = MagicMock()
sys.modules['src.utils.checkpoint'] = _src_utils_ckpt_mod

# Pre-inject src.utils package itself
_src_utils_pkg = types.ModuleType('src.utils')
_src_utils_pkg.__spec__ = importlib.machinery.ModuleSpec('src.utils', None, is_package=True)
_src_utils_pkg.__path__ = []
_src_utils_pkg.config = _mock_config_obj
_src_utils_pkg.logger = MagicMock()
_src_utils_pkg.setup_logger = MagicMock()
_src_utils_pkg.get_llm = MagicMock()
_src_utils_pkg.get_embeddings = MagicMock()
_src_utils_pkg.OCIGenAI = MagicMock()
_src_utils_pkg.OCIGenAIEmbeddings = MagicMock()
_src_utils_pkg.checkpoint_saver = MagicMock()
_src_utils_pkg.OracleCheckpointSaver = MagicMock()
sys.modules['src.utils'] = _src_utils_pkg


class TestMCPServers(unittest.TestCase):
    """Tests for all 10 MCP Tool Servers."""

    def test_kb_server_query(self):
        from src.mcp_servers.kb_server import KBServer
        server = KBServer()
        result = server.query("AWS EC2 OCI equivalent", collection="all", top_k=3)
        self.assertIn("answer", result)
        self.assertIn("retrieved_documents", result)
        self.assertIsInstance(result["retrieved_documents"], list)

    def test_kb_server_service_mapping(self):
        from src.mcp_servers.kb_server import KBServer
        server = KBServer()
        result = server.query_service_mapping("EC2", "AWS")
        self.assertEqual(result["source_service"], "EC2")
        self.assertIn("mapping", result)

    def test_kb_server_health(self):
        from src.mcp_servers.kb_server import KBServer
        server = KBServer()
        health = server.get_health_metrics()
        self.assertEqual(health["server"], "kb")
        self.assertEqual(health["status"], "healthy")

    def test_docs_server(self):
        from src.mcp_servers.docs_server import DocsServer
        server = DocsServer()
        result = server.extract_all("/path/to/document.pdf")
        self.assertIn("text", result)
        self.assertIn("tables", result)
        tables = server.extract_tables("/doc.pdf")
        self.assertIn("tables", tables)
        self.assertGreater(tables["table_count"], 0)

    def test_xls_finops_server(self):
        from src.mcp_servers.xls_finops_server import XlsFinOpsServer
        server = XlsFinOpsServer()
        result = server.extract_cost_breakdown("/bom.xlsx")
        self.assertIn("cost_breakdown", result)
        self.assertGreater(result["cost_breakdown"]["total_monthly_cost"], 0)
        fmt = server.detect_export_format("/aws-cost-report.csv")
        self.assertIn("detected_provider", fmt)

    def test_mapping_server_aws_to_oci(self):
        from src.mcp_servers.mapping_server import MappingServer
        server = MappingServer()
        tests = [
            ("EC2", "Compute Instance"),
            ("S3", "Object Storage"),
            ("RDS", "MySQL HeatWave"),
            ("VPC", "Virtual Cloud Network"),
        ]
        for aws_service, expected_oci in tests:
            result = server.aws_to_oci(aws_service)
            self.assertIn(expected_oci.split("/")[0], result["oci_service"],
                         f"Failed mapping for {aws_service}")

    def test_mapping_server_unknown_service(self):
        from src.mcp_servers.mapping_server import MappingServer
        server = MappingServer()
        result = server.aws_to_oci("SomeUnknownService")
        self.assertIn("source_service", result)
        self.assertLess(result.get("confidence", 1.0), 0.80)

    def test_refarch_server(self):
        from src.mcp_servers.refarch_server import RefArchServer
        server = RefArchServer()
        templates = server.list_templates()
        self.assertGreaterEqual(templates["total"], 4)
        template = server.get_template("landing-zone-v2")
        self.assertTrue(template["found"])
        match = server.match_pattern("three tier web application", ["EC2", "RDS", "ELB"])
        self.assertIn("best_match", match)

    def test_sizing_server(self):
        from src.mcp_servers.sizing_server import SizingServer
        server = SizingServer()
        compute = server.estimate_compute("m5.xlarge")
        self.assertEqual(compute["ocpu"], 2)
        self.assertEqual(compute["memory_gb"], 16)
        self.assertGreater(compute["estimated_monthly_cost_usd"], 0)
        storage = server.estimate_storage("s3", 1000)
        self.assertAlmostEqual(storage["estimated_monthly_cost_usd"], 25.5, places=1)
        network = server.estimate_network(500, num_load_balancers=2)
        self.assertGreater(network["total_monthly_cost_usd"], 0)

    def test_pricing_server(self):
        from src.mcp_servers.pricing_server import PricingServer
        server = PricingServer()
        estimate = server.oci_estimate([
            {"type": "compute", "shape": "VM.Standard.E4.Flex", "ocpu": 2, "memory_gb": 16, "quantity": 3, "name": "app-servers"},
            {"type": "storage", "storage_class": "Object Storage Standard", "size_gb": 1000, "quantity": 1, "name": "data-bucket"},
            {"type": "load_balancer", "quantity": 1, "name": "lb"},
        ])
        self.assertGreater(estimate["total_monthly_cost_usd"], 0)
        self.assertGreater(estimate["total_annual_cost_usd"], estimate["total_monthly_cost_usd"])
        comparison = server.compare_with_source(10000, 6000)
        self.assertEqual(comparison["monthly_savings_usd"], 4000)
        self.assertEqual(comparison["savings_percentage"], 40.0)

    def test_deliverables_server(self):
        from src.mcp_servers.deliverables_server import DeliverablesServer
        server = DeliverablesServer()
        report = server.generate_report({"migration_id": "test-001"})
        self.assertIn("html", report["content"].lower())
        diagram = server.generate_diagram("logical", {})
        self.assertIn("mermaid", diagram["format"])
        runbook = server.generate_runbook({"migration_id": "test-001"})
        self.assertIn("migration_id", runbook)
        bundle = server.bundle_deliverables("test-001", ["report.html", "terraform.zip"])
        self.assertEqual(bundle["artifact_count"], 2)

    def test_terraform_gen_server(self):
        from src.mcp_servers.terraform_gen_server import TerraformGenServer
        server = TerraformGenServer()
        provider = server.generate_provider("us-ashburn-1")
        self.assertIn("oracle/oci", provider["content"])
        self.assertEqual(provider["file_name"], "provider.tf")
        variables = server.generate_variables([{"name": "ssh_public_key", "type": "string", "description": "SSH Key"}])
        self.assertIn("tenancy_ocid", variables["content"])
        self.assertGreaterEqual(variables["variable_count"], 4)
        module = server.generate_module("vcn", "oracle-terraform-modules/vcn/oci", {"compartment_id": "var.compartment_ocid"})
        self.assertIn("vcn", module["content"])

    def test_oci_rm_server(self):
        from src.mcp_servers.oci_rm_server import OCIResourceManagerServer
        server = OCIResourceManagerServer()
        stack = server.create_stack("test-stack", "provider.tf", "ocid1.compartment.oc1..test")
        self.assertIn("stack_id", stack)
        self.assertTrue(stack["stack_id"].startswith("ocid1.ormstack"))
        plan = server.plan_stack(stack["stack_id"])
        self.assertIn("job_id", plan)
        apply = server.apply_stack(stack["stack_id"])
        self.assertIn("job_id", apply)
        job = server.get_job(apply["job_id"])
        self.assertIn("job", job)
        logs = server.get_job_logs(plan["job_id"])
        self.assertGreater(logs["log_count"], 0)


class TestKnowledgeBase(unittest.TestCase):
    """Tests for Oracle 23ai Knowledge Base Manager."""

    def setUp(self):
        from src.knowledge_base.kb_manager import KnowledgeBaseManager
        self.kb = KnowledgeBaseManager()

    def test_baseline_documents_seeded(self):
        stats = self.kb.get_stats()
        self.assertGreaterEqual(stats["total_documents"], 15)

    def test_query_returns_results(self):
        result = self.kb.query("AWS EC2 OCI compute instance")
        self.assertIn("answer", result)
        self.assertIn("retrieved_documents", result)
        self.assertGreater(len(result["retrieved_documents"]), 0)

    def test_query_relevance_scoring(self):
        result = self.kb.query("OCI pricing compute cost")
        docs = result["retrieved_documents"]
        if len(docs) > 1:
            scores = [d["relevance_score"] for d in docs]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_add_and_query_document(self):
        doc_id = self.kb.add_document(
            "Custom migration guide: migrate Redis to OCI Cache with Redis for better performance",
            "best_practices",
            source="test"
        )
        self.assertIsNotNone(doc_id)
        result = self.kb.query("Redis OCI Cache migration")
        self.assertGreater(len(result["retrieved_documents"]), 0)

    def test_collection_filter(self):
        result_all = self.kb.query("OCI services", collection="all")
        result_filtered = self.kb.query("OCI services", collection="service_mappings")
        for doc in result_filtered["retrieved_documents"]:
            self.assertEqual(doc["collection"], "service_mappings")

    def test_service_mapping_query(self):
        result = self.kb.query_service_mapping("EC2", "AWS")
        self.assertIn("mapping_docs", result)
        self.assertEqual(result["source_service"], "EC2")

    def test_best_practices_query(self):
        result = self.kb.query_best_practices("database migration")
        self.assertIn("practices", result)
        self.assertIn("answer", result)

    def test_architecture_patterns_query(self):
        result = self.kb.query_architecture_patterns("three tier web")
        self.assertIn("patterns", result)

    def test_pricing_info_query(self):
        result = self.kb.query_pricing_info("Compute Instance")
        self.assertIn("pricing_docs", result)
        self.assertEqual(result["service"], "Compute Instance")

    def test_compliance_query(self):
        result = self.kb.query_compliance_standards("PCI DSS")
        self.assertIn("compliance_docs", result)

    def test_list_collections(self):
        collections = self.kb.list_collections()
        collection_names = [c["name"] for c in collections]
        expected = ["service_mappings", "best_practices", "architecture_patterns", "pricing_info", "compliance_standards"]
        for name in expected:
            self.assertIn(name, collection_names)

    def test_document_chunking(self):
        long_text = " ".join(["word"] * 1200)
        chunks = self.kb._chunk_document(long_text, chunk_size=500, overlap=50)
        self.assertGreater(len(chunks), 1)


class TestAPIRoutes(unittest.TestCase):
    """Tests for FastAPI route structure."""

    def setUp(self):
        from src.api.routes import router
        self.router = router

    def test_route_count(self):
        self.assertGreaterEqual(len(self.router.routes), 25)

    def test_key_endpoints_present(self):
        paths = [r.path for r in self.router.routes]
        required = [
            "/migrations",
            "/kb/query",
            "/health",
            "/terraform/generate",
            "/terraform/validate",
            "/oci/stacks/create",
            "/projects/export",
            "/projects/import",
            "/deployment/validate/pre",
            "/deployment/validate/post",
            "/deployment/report",
            "/health/mcp-monitor",
        ]
        for path in required:
            self.assertIn(path, paths, f"Missing endpoint: {path}")

    def test_dynamic_endpoints_present(self):
        paths = [r.path for r in self.router.routes]
        dynamic = [
            "/migrations/{migration_id}",
            "/migrations/{migration_id}/discovery-review",
            "/migrations/{migration_id}/archhub-review",
            "/migrations/{migration_id}/livelabs-review",
            "/migrations/{migration_id}/design-review",
            "/migrations/{migration_id}/review",
            "/migrations/{migration_id}/risk-analysis",
            "/migrations/{migration_id}/cost-optimization",
            "/migrations/{migration_id}/phase/analysis",
            "/migrations/{migration_id}/phase/design",
        ]
        for path in dynamic:
            self.assertIn(path, paths, f"Missing dynamic endpoint: {path}")


class TestPhase5Routing(unittest.TestCase):
    """Tests for Phase 5 implementation pathway routing."""

    def setUp(self):
        from src.models.state_schema import MigrationState, ImplementationStrategy
        from src.agents.phase5_implementation import (
            route_by_strategy, OCI_COMPONENT_CATALOG, SUPPORTED_FRAMEWORKS
        )
        self.MigrationState = MigrationState
        self.ImplementationStrategy = ImplementationStrategy
        self.route_by_strategy = route_by_strategy
        self.OCI_COMPONENT_CATALOG = OCI_COMPONENT_CATALOG
        self.SUPPORTED_FRAMEWORKS = SUPPORTED_FRAMEWORKS

    def _make_state(self, strategy):
        state = self.MigrationState(migration_id='test-route', source_provider='AWS')
        state.implementation.strategy = strategy
        return state

    def test_route_pre_packaged(self):
        state = self._make_state(self.ImplementationStrategy.PRE_PACKAGED)
        self.assertEqual(self.route_by_strategy(state), "pre_packaged")

    def test_route_dynamic_terraform(self):
        state = self._make_state(self.ImplementationStrategy.DYNAMIC_TERRAFORM)
        self.assertEqual(self.route_by_strategy(state), "dynamic_terraform")

    def test_route_third_party(self):
        state = self._make_state(self.ImplementationStrategy.THIRD_PARTY)
        self.assertEqual(self.route_by_strategy(state), "third_party")

    def test_route_default_is_dynamic(self):
        state = self.MigrationState(migration_id='test', source_provider='AWS')
        # No strategy set - should default to dynamic_terraform
        self.assertEqual(self.route_by_strategy(state), "dynamic_terraform")

    def test_component_catalog(self):
        self.assertGreaterEqual(len(self.OCI_COMPONENT_CATALOG), 4)
        ids = [c["component_id"] for c in self.OCI_COMPONENT_CATALOG]
        self.assertIn("landing-zone-v2", ids)
        self.assertIn("three-tier-web-app", ids)
        for comp in self.OCI_COMPONENT_CATALOG:
            self.assertIn("name", comp)
            self.assertIn("description", comp)
            self.assertIn("category", comp)
            self.assertIn("parameters", comp)

    def test_supported_frameworks(self):
        self.assertGreaterEqual(len(self.SUPPORTED_FRAMEWORKS), 4)
        ids = [f["framework_id"] for f in self.SUPPORTED_FRAMEWORKS]
        self.assertIn("pulumi", ids)
        self.assertIn("ansible", ids)
        self.assertIn("terraform-cdk", ids)


class TestStateSchema(unittest.TestCase):
    """Tests for MigrationState schema."""

    def test_create_migration_state(self):
        from src.models.state_schema import create_migration_state
        state = create_migration_state(
            migration_id="mig-001",
            user_context="Migrate 3-tier app from AWS",
            source_provider="AWS",
            target_region="eu-frankfurt-1"
        )
        self.assertEqual(state.migration_id, "mig-001")
        self.assertEqual(state.source_provider, "AWS")
        self.assertEqual(state.target_region, "eu-frankfurt-1")

    def test_implementation_strategies(self):
        from src.models.state_schema import ImplementationStrategy
        self.assertEqual(ImplementationStrategy.PRE_PACKAGED.value, "pre_packaged")
        self.assertEqual(ImplementationStrategy.DYNAMIC_TERRAFORM.value, "dynamic_terraform")
        self.assertEqual(ImplementationStrategy.THIRD_PARTY.value, "third_party")

    def test_review_decisions(self):
        from src.models.state_schema import ReviewDecision
        self.assertEqual(ReviewDecision.APPROVE.value, "approve")
        self.assertEqual(ReviewDecision.REQUEST_CHANGES.value, "request_changes")
        self.assertEqual(ReviewDecision.REJECT.value, "reject")

    def test_phase_status_transitions(self):
        from src.models.state_schema import PhaseStatus
        self.assertEqual(PhaseStatus.PENDING.value, "pending")
        self.assertEqual(PhaseStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(PhaseStatus.COMPLETED.value, "completed")
        self.assertEqual(PhaseStatus.WAITING_REVIEW.value, "waiting_review")


if __name__ == "__main__":
    # Run with verbose output
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestMCPServers))
    suite.addTests(loader.loadTestsFromTestCase(TestKnowledgeBase))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIRoutes))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase5Routing))
    suite.addTests(loader.loadTestsFromTestCase(TestStateSchema))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
