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
from src.mcp_servers.mapping_server   import mapping_server
from src.mcp_servers.sizing_server    import sizing_server
from src.mcp_servers.pricing_server   import pricing_server
from src.mcp_servers.refarch_server   import refarch_server
from src.mcp_servers.terraform_gen_server import terraform_gen_server
from src.mcp_servers.oci_rm_server    import oci_rm_server


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
# CONVENIENCE FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def get_all_tools() -> List[BaseTool]:
    """Return all OCI migration LangChain tools as a list."""
    return [
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
    ]
