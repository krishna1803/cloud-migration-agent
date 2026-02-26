"""
LangChain Tool wrappers for OCI Migration MCP Servers.

Each tool calls the corresponding MCP server singleton and returns a
JSON-serialisable string so the LLM can reason over the result.
"""
import json
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

# MCP server singletons
from src.mcp_servers.mapping_server         import mapping_server
from src.mcp_servers.sizing_server          import sizing_server
from src.mcp_servers.pricing_server         import pricing_server
from src.mcp_servers.refarch_server         import refarch_server
from src.mcp_servers.terraform_gen_server   import terraform_gen_server
from src.mcp_servers.oci_rm_server          import oci_rm_server
from src.mcp_servers.oracle_archhub_server  import oracle_archhub_server
from src.mcp_servers.oracle_livelabs_server import oracle_livelabs_server
from src.mcp_servers.terraform_validator_server import terraform_validator_server
from src.mcp_servers.dependency_analysis_server import dependency_analysis_server
from src.mcp_servers.project_export_server  import project_export_server
from src.mcp_servers.deployment_monitor_server import deployment_monitor_server


def _j(obj: Any) -> str:
    """Compact JSON serialiser — returns a string the LLM can parse."""
    return json.dumps(obj, indent=2, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE MAPPING TOOL
# ─────────────────────────────────────────────────────────────────────────────

class ServiceMappingInput(BaseModel):
    services: List[str] = Field(
        description="List of source cloud service names, e.g. ['EC2', 'S3', 'RDS']"
    )
    source_provider: str = Field(
        default="AWS",
        description="Source cloud provider: 'AWS', 'Azure', or 'GCP'"
    )


class ServiceMappingTool(BaseTool):
    name: str = "oci_service_mapping"
    description: str = (
        "Maps source cloud services (AWS / Azure / GCP) to their OCI equivalents. "
        "Returns OCI service names, Terraform resource types, confidence scores, "
        "migration effort, and migration notes. "
        "Use this to understand what OCI services replace source services."
    )
    args_schema: Type[BaseModel] = ServiceMappingInput
    return_direct: bool = False

    def _run(self, services: List[str], source_provider: str = "AWS") -> str:
        result = mapping_server.bulk_map(services, source_provider)
        return _j(result)

    async def _arun(self, services: List[str], source_provider: str = "AWS") -> str:
        return self._run(services, source_provider)


# ─────────────────────────────────────────────────────────────────────────────
# RESOURCE SIZING TOOL
# ─────────────────────────────────────────────────────────────────────────────

class ResourceSizingInput(BaseModel):
    instance_type: str = Field(
        description="Source instance type, e.g. 'm5.xlarge', 'Standard_D4s_v3', 'n2-standard-4'"
    )
    source_provider: str = Field(
        default="AWS",
        description="Source cloud provider: 'AWS', 'Azure', 'GCP', or 'On-Premises'"
    )
    workload_type: str = Field(
        default="general",
        description=(
            "Workload hint for shape selection. Options: "
            "general, web, app, compute, memory, database, io-intensive, "
            "microservices, containers, ai, inference, batch, hpc"
        )
    )
    rightsizing_factor: float = Field(
        default=1.0,
        description="Scale factor for right-sizing (0.5-1.5). Use 0.8 to downsize 20%."
    )


class ResourceSizingTool(BaseTool):
    name: str = "oci_resource_sizing"
    description: str = (
        "Maps a source cloud instance type to the best-fit OCI compute shape. "
        "Returns the recommended OCI shape, OCPU/memory specs, monthly cost estimate, "
        "and cost savings vs source. Supports AWS EC2, Azure VM, and GCP machine types."
    )
    args_schema: Type[BaseModel] = ResourceSizingInput
    return_direct: bool = False

    def _run(
        self,
        instance_type: str,
        source_provider: str = "AWS",
        workload_type: str = "general",
        rightsizing_factor: float = 1.0,
    ) -> str:
        result = sizing_server.estimate_compute(
            instance_type, source_provider, workload_type, rightsizing_factor
        )
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# PRICING ESTIMATION TOOL
# ─────────────────────────────────────────────────────────────────────────────

class PricingInput(BaseModel):
    resources: List[Dict[str, Any]] = Field(
        description=(
            "List of OCI resources to price. Each item is a dict with at minimum "
            "'type' and 'name'. Type-specific fields: "
            "compute: shape, ocpu, memory_gb, quantity; "
            "storage: storage_class, size_gb; "
            "database: db_service, ocpu, storage_tb; "
            "load_balancer: lb_type ('flexible'|'network'), quantity; "
            "functions: gb_seconds_month, million_calls_month."
        )
    )


class PricingEstimationTool(BaseTool):
    name: str = "oci_pricing_estimation"
    description: str = (
        "Estimates OCI monthly and annual costs for a list of resources. "
        "Uses the official OCI Pay-As-You-Go price list (2024/2025). "
        "Returns per-resource line items, totals, and a note about committed-use discounts. "
        "Supports compute, storage, database, load balancers, and serverless functions."
    )
    args_schema: Type[BaseModel] = PricingInput
    return_direct: bool = False

    def _run(self, resources: List[Dict[str, Any]]) -> str:
        result = pricing_server.oci_estimate(resources)
        return _j(result)

    async def _arun(self, resources: List[Dict[str, Any]]) -> str:
        return self._run(resources)


class SavingsComparisonInput(BaseModel):
    source_monthly_cost: float = Field(description="Current cloud monthly cost in USD")
    oci_monthly_cost:    float = Field(description="Estimated OCI monthly cost in USD")
    migration_cost_usd:  float = Field(default=0.0, description="One-time migration cost in USD")


class SavingsComparisonTool(BaseTool):
    name: str = "oci_savings_comparison"
    description: str = (
        "Compares current cloud spend vs OCI and calculates ROI: "
        "monthly savings, annual savings, payback period, and 3-year net savings."
    )
    args_schema: Type[BaseModel] = SavingsComparisonInput
    return_direct: bool = False

    def _run(
        self,
        source_monthly_cost: float,
        oci_monthly_cost: float,
        migration_cost_usd: float = 0.0,
    ) -> str:
        result = pricing_server.compare_with_source(
            source_monthly_cost, oci_monthly_cost, migration_cost_usd
        )
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE ARCHITECTURE TOOL
# ─────────────────────────────────────────────────────────────────────────────

class RefArchInput(BaseModel):
    architecture_description: str = Field(
        description="Natural-language description of the workload or current architecture"
    )
    services: Optional[List[str]] = Field(
        default=None,
        description="List of OCI services or keywords from service mapping (optional)"
    )
    source_provider: Optional[str] = Field(
        default=None,
        description="Source cloud provider to filter architectures: 'AWS', 'Azure', 'GCP', 'On-Premises'"
    )
    complexity_preference: Optional[str] = Field(
        default=None,
        description="Preferred complexity: 'low', 'medium', or 'high'"
    )


class RefArchTool(BaseTool):
    name: str = "oci_reference_architecture"
    description: str = (
        "Finds the best-matching OCI Architecture Center reference pattern for a workload. "
        "Returns the top match plus alternatives, with: component list, estimated cost, "
        "Terraform module source, Mermaid architecture diagram, and OCI documentation URL. "
        "Use this after service mapping to select the right target architecture."
    )
    args_schema: Type[BaseModel] = RefArchInput
    return_direct: bool = False

    def _run(
        self,
        architecture_description: str,
        services: Optional[List[str]] = None,
        source_provider: Optional[str] = None,
        complexity_preference: Optional[str] = None,
    ) -> str:
        result = refarch_server.match_pattern(
            architecture_description,
            services or [],
            source_provider,
            complexity_preference,
        )
        # Strip the heavy diagram field from non-primary results to save tokens
        if result.get("alternatives"):
            for alt in result["alternatives"]:
                alt.pop("diagram_mermaid", None)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class ListRefArchInput(BaseModel):
    category: Optional[str] = Field(
        default=None,
        description="Filter by category: Foundation, Web Application, Kubernetes, Data & Analytics, etc."
    )


class ListRefArchTool(BaseTool):
    name: str = "oci_list_reference_architectures"
    description: str = (
        "Lists all available OCI Architecture Center reference patterns, "
        "optionally filtered by category. Use this to discover what patterns are available."
    )
    args_schema: Type[BaseModel] = ListRefArchInput
    return_direct: bool = False

    def _run(self, category: Optional[str] = None) -> str:
        result = refarch_server.list_templates(category)
        return _j(result)

    async def _arun(self, category: Optional[str] = None) -> str:
        return self._run(category)


# ─────────────────────────────────────────────────────────────────────────────
# TERRAFORM GENERATION TOOL
# ─────────────────────────────────────────────────────────────────────────────

class TerraformGenInput(BaseModel):
    resource_type: str = Field(
        description=(
            "OCI Terraform resource type, e.g.: "
            "oci_core_vcn, oci_core_instance, oci_load_balancer_load_balancer, "
            "oci_database_autonomous_database, oci_mysql_mysql_db_system, "
            "oci_containerengine_cluster, oci_objectstorage_bucket, oci_kms_vault"
        )
    )
    resource_name: str = Field(description="Terraform resource logical name (snake_case)")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Resource-specific configuration overrides (shape, ocpu, cidr_block, etc.)"
    )


class TerraformGenTool(BaseTool):
    name: str = "oci_terraform_generate"
    description: str = (
        "Generates production-ready OCI Terraform HCL for a specific resource type. "
        "Returns the resource block content. Use oci_terraform_generate_project for "
        "complete multi-file projects."
    )
    args_schema: Type[BaseModel] = TerraformGenInput
    return_direct: bool = False

    def _run(
        self, resource_type: str, resource_name: str, config: Dict[str, Any]
    ) -> str:
        result = terraform_gen_server.generate_resource(resource_type, resource_name, config)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class TerraformProjectInput(BaseModel):
    project_name: str = Field(default="migration", description="Project name prefix for all resources")
    region: str = Field(default="us-ashburn-1", description="Target OCI region")


class TerraformProjectTool(BaseTool):
    name: str = "oci_terraform_generate_project"
    description: str = (
        "Generates a complete OCI Terraform project with multiple .tf files "
        "for a 3-tier web application (VCN, Load Balancer, Compute, Autonomous DB). "
        "Returns a dict of {filename: content} ready for deployment."
    )
    args_schema: Type[BaseModel] = TerraformProjectInput
    return_direct: bool = False

    def _run(self, project_name: str = "migration", region: str = "us-ashburn-1") -> str:
        result = terraform_gen_server.generate_three_tier_project(project_name, region)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# OCI RESOURCE MANAGER TOOL
# ─────────────────────────────────────────────────────────────────────────────

class CreateStackInput(BaseModel):
    stack_name:       str  = Field(description="Display name for the OCI Resource Manager stack")
    terraform_config: str  = Field(description="Terraform HCL content (main.tf)")
    compartment_id:   str  = Field(default="", description="Target compartment OCID (uses config default if empty)")
    variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Terraform input variables as key-value pairs"
    )


class OCIResourceManagerTool(BaseTool):
    name: str = "oci_resource_manager_create"
    description: str = (
        "Creates an OCI Resource Manager (managed Terraform) stack from HCL content. "
        "When OCI credentials are configured, uses the real OCI SDK; "
        "otherwise uses a mock that returns realistic OCIDs for testing. "
        "Returns the stack_id to use with plan/apply tools."
    )
    args_schema: Type[BaseModel] = CreateStackInput
    return_direct: bool = False

    def _run(
        self,
        stack_name: str,
        terraform_config: str,
        compartment_id: str = "",
        variables: Optional[Dict[str, str]] = None,
    ) -> str:
        result = oci_rm_server.create_stack(
            stack_name, terraform_config, compartment_id, variables
        )
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class PlanStackInput(BaseModel):
    stack_id: str = Field(description="OCI Resource Manager stack OCID")


class PlanStackTool(BaseTool):
    name: str = "oci_resource_manager_plan"
    description: str = "Runs a Terraform PLAN job on an OCI Resource Manager stack. Returns job_id and plan output."
    args_schema: Type[BaseModel] = PlanStackInput
    return_direct: bool = False

    def _run(self, stack_id: str) -> str:
        result = oci_rm_server.plan_stack(stack_id)
        return _j(result)

    async def _arun(self, stack_id: str) -> str:
        return self._run(stack_id)


class ApplyStackInput(BaseModel):
    stack_id:    str  = Field(description="OCI Resource Manager stack OCID")
    plan_job_id: str  = Field(default="", description="Plan job OCID to apply (empty = auto-approved)")


class ApplyStackTool(BaseTool):
    name: str = "oci_resource_manager_apply"
    description: str = "Applies a Terraform plan on an OCI Resource Manager stack. Returns job_id and status."
    args_schema: Type[BaseModel] = ApplyStackInput
    return_direct: bool = False

    def _run(self, stack_id: str, plan_job_id: str = "") -> str:
        result = oci_rm_server.apply_stack(stack_id, plan_job_id or None)
        return _j(result)

    async def _arun(self, stack_id: str, plan_job_id: str = "") -> str:
        return self._run(stack_id, plan_job_id)


class GetJobInput(BaseModel):
    job_id: str = Field(description="OCI Resource Manager job OCID")


class GetJobTool(BaseTool):
    name: str = "oci_resource_manager_job_status"
    description: str = "Gets the status of an OCI Resource Manager job (PLAN/APPLY/DESTROY)."
    args_schema: Type[BaseModel] = GetJobInput
    return_direct: bool = False

    def _run(self, job_id: str) -> str:
        return _j(oci_rm_server.get_job(job_id))

    async def _arun(self, job_id: str) -> str:
        return self._run(job_id)


class GetJobLogsInput(BaseModel):
    job_id: str = Field(description="OCI Resource Manager job OCID")


class GetJobLogsTool(BaseTool):
    name: str = "oci_resource_manager_job_logs"
    description: str = "Retrieves Terraform execution logs for an OCI Resource Manager job."
    args_schema: Type[BaseModel] = GetJobLogsInput
    return_direct: bool = False

    def _run(self, job_id: str) -> str:
        return _j(oci_rm_server.get_job_logs(job_id))

    async def _arun(self, job_id: str) -> str:
        return self._run(job_id)


# ─────────────────────────────────────────────────────────────────────────────
# OCI SHAPE CATALOGUE TOOL
# ─────────────────────────────────────────────────────────────────────────────

class ShapeCatalogueInput(BaseModel):
    workload_type: str = Field(
        default="general",
        description="Workload type for shape recommendations: general, web, compute, memory, database, ai, etc."
    )
    prefer_arm: bool = Field(default=False, description="Prefer ARM (Ampere A1) shapes for lower cost")
    min_ocpu: int = Field(default=2, description="Minimum OCPU count required")
    min_memory_gb: int = Field(default=8, description="Minimum memory in GB required")


class ShapeCatalogueTool(BaseTool):
    name: str = "oci_shape_recommendation"
    description: str = (
        "Recommends OCI compute shapes for a given workload type and resource requirements. "
        "Returns top 3 shapes with OCPU/memory specs and hourly/monthly cost."
    )
    args_schema: Type[BaseModel] = ShapeCatalogueInput
    return_direct: bool = False

    def _run(
        self,
        workload_type: str = "general",
        prefer_arm: bool = False,
        min_ocpu: int = 2,
        min_memory_gb: int = 8,
    ) -> str:
        result = sizing_server.recommend_shape(workload_type, min_ocpu, min_memory_gb, prefer_arm)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# ORACLE ARCHITECTURE HUB TOOL
# ─────────────────────────────────────────────────────────────────────────────

class ArchHubSearchInput(BaseModel):
    query: str = Field(description="Natural-language search string (e.g. 'three-tier web app', 'kubernetes migration')")
    category: Optional[str] = Field(default=None, description="Category filter (e.g. 'Web Application', 'Kubernetes', 'Database Migration')")
    workload_type: Optional[str] = Field(default=None, description="Workload hint (e.g. 'database', 'microservices', 'analytics')")
    max_results: int = Field(default=5, description="Maximum results to return")


class ArchHubSearchTool(BaseTool):
    name: str = "archhub_search"
    description: str = (
        "Search Oracle Architecture Hub for reference architectures matching a workload description. "
        "Returns architecture titles, categories, services used, Terraform module sources, and documentation URLs. "
        "Use this in Phase 2 Analysis to discover Oracle reference patterns for the target architecture."
    )
    args_schema: Type[BaseModel] = ArchHubSearchInput
    return_direct: bool = False

    def _run(self, query: str, category: Optional[str] = None, workload_type: Optional[str] = None, max_results: int = 5) -> str:
        result = oracle_archhub_server.search(query, category, workload_type, max_results)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class ArchHubExtractInput(BaseModel):
    arch_id: str = Field(description="Architecture ID from archhub_search results (e.g. 'arch-001')")


class ArchHubExtractTool(BaseTool):
    name: str = "archhub_extract_architecture"
    description: str = (
        "Extract structured component details from a specific Oracle Architecture Hub pattern. "
        "Returns components, services, migration suitability, and Terraform module reference. "
        "Use after archhub_search to get full architecture details."
    )
    args_schema: Type[BaseModel] = ArchHubExtractInput
    return_direct: bool = False

    def _run(self, arch_id: str) -> str:
        result = oracle_archhub_server.extract_architecture(arch_id)
        return _j(result)

    async def _arun(self, arch_id: str) -> str:
        return self._run(arch_id)


# ─────────────────────────────────────────────────────────────────────────────
# ORACLE LIVE LABS TOOL
# ─────────────────────────────────────────────────────────────────────────────

class LiveLabsSearchInput(BaseModel):
    query: str = Field(description="Search string for workshops (e.g. 'kubernetes migration', 'terraform iac')")
    focus_area: Optional[str] = Field(default=None, description="Focus area filter (e.g. 'Cloud Migration', 'Database', 'Kubernetes')")
    level: Optional[str] = Field(default=None, description="Workshop level: 'Beginner', 'Intermediate', or 'Advanced'")
    max_results: int = Field(default=5, description="Maximum workshops to return")


class LiveLabsSearchTool(BaseTool):
    name: str = "livelabs_search"
    description: str = (
        "Search Oracle Live Labs for hands-on workshops relevant to the migration. "
        "Returns workshop titles, focus areas, duration, lab steps, and workshop URLs. "
        "Use in Phase 2 Analysis to recommend learning resources and migration workshops."
    )
    args_schema: Type[BaseModel] = LiveLabsSearchInput
    return_direct: bool = False

    def _run(self, query: str, focus_area: Optional[str] = None, level: Optional[str] = None, max_results: int = 5) -> str:
        result = oracle_livelabs_server.search(query, focus_area, level, max_results)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# TERRAFORM VALIDATOR TOOL
# ─────────────────────────────────────────────────────────────────────────────

class TerraformValidateInput(BaseModel):
    hcl_content: str = Field(description="Terraform HCL content string to validate")
    filename: str = Field(default="main.tf", description="Source filename for error messages")


class TerraformValidateTool(BaseTool):
    name: str = "terraform_validate_syntax"
    description: str = (
        "Validate Terraform HCL syntax by checking brace balance, required blocks, and resource extraction. "
        "Returns is_valid flag, errors, warnings, and resource summary. "
        "Use in Phase 5 Implementation after generating Terraform code."
    )
    args_schema: Type[BaseModel] = TerraformValidateInput
    return_direct: bool = False

    def _run(self, hcl_content: str, filename: str = "main.tf") -> str:
        result = terraform_validator_server.validate_syntax(hcl_content, filename)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class TerraformSecurityScanInput(BaseModel):
    hcl_content: str = Field(description="Terraform HCL content to security scan")
    filename: str = Field(default="main.tf", description="Source filename for finding messages")
    severity_filter: Optional[str] = Field(default=None, description="Filter findings by severity: 'HIGH', 'MEDIUM', or 'LOW'")


class TerraformSecurityScanTool(BaseTool):
    name: str = "terraform_security_scan"
    description: str = (
        "Scan Terraform HCL for OCI security policy violations: open SSH/RDP ports, "
        "public storage buckets, hardcoded credentials, missing tags, and more. "
        "Returns findings with severity and remediation recommendations. "
        "Use in Phase 5 Implementation to validate generated code before deployment."
    )
    args_schema: Type[BaseModel] = TerraformSecurityScanInput
    return_direct: bool = False

    def _run(self, hcl_content: str, filename: str = "main.tf", severity_filter: Optional[str] = None) -> str:
        result = terraform_validator_server.security_scan(hcl_content, filename, severity_filter)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# DEPENDENCY ANALYSIS TOOLS
# ─────────────────────────────────────────────────────────────────────────────

class AnalyzeDepsInput(BaseModel):
    modules: List[Dict[str, Any]] = Field(
        description=(
            "List of module descriptors. Each dict has: "
            "'name' (str), 'type' (OCI resource type), 'depends_on' (list of dependency names)"
        )
    )
    hcl_content: Optional[str] = Field(default=None, description="Optional raw HCL to auto-extract dependencies")


class AnalyzeDependenciesTool(BaseTool):
    name: str = "analyze_terraform_dependencies"
    description: str = (
        "Build a dependency graph from Terraform module definitions or raw HCL. "
        "Returns the dependency graph, node metadata, and deployment time estimates. "
        "Use before optimize_deployment_waves to understand resource ordering."
    )
    args_schema: Type[BaseModel] = AnalyzeDepsInput
    return_direct: bool = False

    def _run(self, modules: List[Dict[str, Any]], hcl_content: Optional[str] = None) -> str:
        result = dependency_analysis_server.analyze_terraform_dependencies(modules, hcl_content)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class OptimizeWavesInput(BaseModel):
    graph: Dict[str, List[str]] = Field(description="Dependency graph {node_name: [dependency_names]}")
    node_times: Optional[Dict[str, int]] = Field(default=None, description="Per-node deploy time overrides in seconds")


class OptimizeDeploymentWavesTool(BaseTool):
    name: str = "optimize_deployment_waves"
    description: str = (
        "Compute optimal parallel deployment waves using topological sort. "
        "Resources in the same wave can be deployed in parallel. "
        "Returns ordered waves with timing estimates for the deployment plan. "
        "Use in Phase 5 Implementation to optimize deployment order."
    )
    args_schema: Type[BaseModel] = OptimizeWavesInput
    return_direct: bool = False

    def _run(self, graph: Dict[str, List[str]], node_times: Optional[Dict[str, int]] = None) -> str:
        result = dependency_analysis_server.optimize_deployment_waves(graph, node_times)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class GenerateDiagramInput(BaseModel):
    graph: Dict[str, List[str]] = Field(description="Dependency graph {node_name: [dependency_names]}")
    title: str = Field(default="OCI Deployment Dependencies", description="Diagram title")


class GenerateDependencyDiagramTool(BaseTool):
    name: str = "generate_dependency_diagram"
    description: str = (
        "Generate a Mermaid LR diagram visualizing Terraform resource dependencies. "
        "Returns the diagram string for display in the UI or inclusion in deliverables. "
        "Use in Phase 3 Design or Phase 5 Implementation."
    )
    args_schema: Type[BaseModel] = GenerateDiagramInput
    return_direct: bool = False

    def _run(self, graph: Dict[str, List[str]], title: str = "OCI Deployment Dependencies") -> str:
        result = dependency_analysis_server.generate_dependency_diagram(graph, title)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# PROJECT EXPORT TOOL
# ─────────────────────────────────────────────────────────────────────────────

class ExportProjectInput(BaseModel):
    project_name: str = Field(description="Project name used for the archive filename")
    files: Dict[str, str] = Field(description="Dict of {filename: content} for all Terraform files")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata to include in the manifest")


class ExportProjectTool(BaseTool):
    name: str = "export_project_as_zip"
    description: str = (
        "Export a Terraform project as a base64-encoded ZIP archive for download. "
        "Returns export_id, zip_base64, and file manifest for tracking. "
        "Use in Phase 5 Implementation when user selects 'Export for manual editing'."
    )
    args_schema: Type[BaseModel] = ExportProjectInput
    return_direct: bool = False

    def _run(self, project_name: str, files: Dict[str, str], metadata: Optional[Dict[str, Any]] = None) -> str:
        result = project_export_server.export_as_zip(project_name, files, metadata)
        # Omit the large zip_base64 from LLM response (too large for context)
        result_trimmed = {k: v for k, v in result.items() if k != "zip_base64"}
        result_trimmed["zip_available"] = True
        return _j(result_trimmed)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class ImportProjectInput(BaseModel):
    export_id: str = Field(description="The export_id from a previous export_project_as_zip call")
    modified_files: Dict[str, str] = Field(description="Dict of {filename: content} with the modified project files")


class ImportProjectTool(BaseTool):
    name: str = "import_project"
    description: str = (
        "Import a modified Terraform project, detecting changes vs. the original export. "
        "Returns change summary (added/modified/deleted/unchanged files). "
        "Use in Phase 5 Implementation after user has edited the exported project."
    )
    args_schema: Type[BaseModel] = ImportProjectInput
    return_direct: bool = False

    def _run(self, export_id: str, modified_files: Dict[str, str]) -> str:
        result = project_export_server.import_project(export_id, modified_files)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# DEPLOYMENT MONITOR TOOLS
# ─────────────────────────────────────────────────────────────────────────────

class PreDeploymentValidationInput(BaseModel):
    compartment_id: str = Field(description="Target OCI compartment OCID")
    region: str = Field(default="us-ashburn-1", description="Target OCI region")
    planned_resources: Optional[List[str]] = Field(default=None, description="List of resource types to be deployed")


class PreDeploymentValidationTool(BaseTool):
    name: str = "validate_pre_deployment"
    description: str = (
        "Validate OCI environment readiness before deploying: checks connectivity, "
        "IAM permissions, service quotas, and VCN CIDR conflicts. "
        "Returns pass/fail per check and blocking failures. "
        "Use at the start of Phase 6 Deployment."
    )
    args_schema: Type[BaseModel] = PreDeploymentValidationInput
    return_direct: bool = False

    def _run(self, compartment_id: str, region: str = "us-ashburn-1", planned_resources: Optional[List[str]] = None) -> str:
        result = deployment_monitor_server.validate_pre_deployment(compartment_id, region, planned_resources)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class PostDeploymentValidationInput(BaseModel):
    deployment_id: str = Field(description="Migration/deployment ID")
    stack_id: Optional[str] = Field(default=None, description="OCI Resource Manager stack OCID")


class PostDeploymentValidationTool(BaseTool):
    name: str = "validate_post_deployment"
    description: str = (
        "Validate deployed OCI infrastructure: checks resource creation, compute health, "
        "network connectivity, load balancer backends, and security configuration. "
        "Returns overall health status. Use after Terraform apply in Phase 6."
    )
    args_schema: Type[BaseModel] = PostDeploymentValidationInput
    return_direct: bool = False

    def _run(self, deployment_id: str, stack_id: Optional[str] = None) -> str:
        result = deployment_monitor_server.validate_post_deployment(deployment_id, stack_id)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class MonitorDeploymentInput(BaseModel):
    deployment_id: str = Field(description="Deployment/migration ID for tracking")
    job_id: Optional[str] = Field(default=None, description="OCI Resource Manager job OCID")


class MonitorDeploymentTool(BaseTool):
    name: str = "monitor_deployment"
    description: str = (
        "Monitor active OCI deployment progress: tracks resource creation, "
        "completion percentage, ETA, and current operation. "
        "Use during Phase 6 Deployment to track Terraform apply progress."
    )
    args_schema: Type[BaseModel] = MonitorDeploymentInput
    return_direct: bool = False

    def _run(self, deployment_id: str, job_id: Optional[str] = None) -> str:
        result = deployment_monitor_server.monitor_deployment(deployment_id, job_id)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


class GenerateDeploymentReportInput(BaseModel):
    deployment_id: str = Field(description="Deployment/migration ID")
    migration_name: str = Field(description="Human-readable migration project name")
    source_cloud: str = Field(default="AWS", description="Source cloud provider")
    target_region: str = Field(default="us-ashburn-1", description="OCI target region")


class GenerateDeploymentReportTool(BaseTool):
    name: str = "generate_deployment_report"
    description: str = (
        "Generate a comprehensive post-deployment summary report with executive summary, "
        "infrastructure inventory, validation results, and next steps. "
        "Use at the end of Phase 6 Deployment to produce final deliverables."
    )
    args_schema: Type[BaseModel] = GenerateDeploymentReportInput
    return_direct: bool = False

    def _run(self, deployment_id: str, migration_name: str, source_cloud: str = "AWS", target_region: str = "us-ashburn-1") -> str:
        result = deployment_monitor_server.generate_deployment_report(deployment_id, migration_name, source_cloud, target_region)
        return _j(result)

    async def _arun(self, **kwargs: Any) -> str:
        return self._run(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def get_all_tools() -> List[BaseTool]:
    """Return all OCI migration LangChain tools as a list."""
    return [
        # Existing tools
        ServiceMappingTool(),
        ResourceSizingTool(),
        PricingEstimationTool(),
        SavingsComparisonTool(),
        RefArchTool(),
        ListRefArchTool(),
        TerraformGenTool(),
        TerraformProjectTool(),
        OCIResourceManagerTool(),
        PlanStackTool(),
        ApplyStackTool(),
        GetJobTool(),
        GetJobLogsTool(),
        ShapeCatalogueTool(),
        # New tools (v4.1.0)
        ArchHubSearchTool(),
        ArchHubExtractTool(),
        LiveLabsSearchTool(),
        TerraformValidateTool(),
        TerraformSecurityScanTool(),
        AnalyzeDependenciesTool(),
        OptimizeDeploymentWavesTool(),
        GenerateDependencyDiagramTool(),
        ExportProjectTool(),
        ImportProjectTool(),
        PreDeploymentValidationTool(),
        PostDeploymentValidationTool(),
        MonitorDeploymentTool(),
        GenerateDeploymentReportTool(),
    ]
