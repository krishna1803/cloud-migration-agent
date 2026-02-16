"""
State schema for the Cloud Migration Agent Platform.

Defines the complete state structure that flows through all 6 phases
of the migration workflow. Aligned with spec v4.0.0.
"""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class ImplementationStrategy(str, Enum):
    PRE_PACKAGED = "pre_packaged"
    DYNAMIC_TERRAFORM = "dynamic_terraform"
    THIRD_PARTY = "third_party"


# Phase 1: Discovery Models
class DiscoveredService(BaseModel):
    service_name: str = ""
    provider: str = ""
    resource_type: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NetworkArchitecture(BaseModel):
    vpcs: List[Dict[str, Any]] = Field(default_factory=list)
    subnets: List[Dict[str, Any]] = Field(default_factory=list)
    security_groups: List[Dict[str, Any]] = Field(default_factory=list)
    route_tables: List[Dict[str, Any]] = Field(default_factory=list)
    load_balancers: List[Dict[str, Any]] = Field(default_factory=list)


class ComputeResource(BaseModel):
    instance_id: str = ""
    instance_type: str = ""
    vcpus: int = 0
    memory_gb: float = 0.0
    storage_gb: float = 0.0
    os: str = ""
    tags: Dict[str, str] = Field(default_factory=dict)


class StorageResource(BaseModel):
    resource_id: str = ""
    storage_type: str = ""
    size_gb: float = 0.0
    iops: Optional[int] = None
    throughput_mbps: Optional[int] = None


class SecurityPosture(BaseModel):
    iam_roles: List[Dict[str, Any]] = Field(default_factory=list)
    policies: List[Dict[str, Any]] = Field(default_factory=list)
    encryption: Dict[str, Any] = Field(default_factory=dict)
    compliance_requirements: List[str] = Field(default_factory=list)


class Gap(BaseModel):
    category: str = ""
    description: str = ""
    severity: Literal["low", "medium", "high"] = "medium"
    clarification_question: str = ""


class DiscoveryState(BaseModel):
    discovered_services: List[DiscoveredService] = Field(default_factory=list)
    network_architecture: Optional[NetworkArchitecture] = None
    compute_resources: List[ComputeResource] = Field(default_factory=list)
    storage_resources: List[StorageResource] = Field(default_factory=list)
    security_posture: Optional[SecurityPosture] = None
    gaps_identified: List[Gap] = Field(default_factory=list)
    discovery_confidence: float = 0.0
    clarifications_requested: List[str] = Field(default_factory=list)
    clarifications_received: Dict[str, str] = Field(default_factory=dict)
    kb_intelligence: Dict[str, Any] = Field(default_factory=dict)


# Phase 2: Analysis Models
class OCIServiceMapping(BaseModel):
    source_service: str = ""
    oci_service: str = ""
    mapping_confidence: float = 0.0
    alternatives: List[str] = Field(default_factory=list)
    reasoning: str = ""


class ArchHubReference(BaseModel):
    architecture_id: str = ""
    title: str = ""
    description: str = ""
    diagram_url: str = ""
    components: List[str] = Field(default_factory=list)
    match_score: float = 0.0


class LiveLabsWorkshop(BaseModel):
    workshop_id: str = ""
    title: str = ""
    description: str = ""
    url: str = ""
    relevance_score: float = 0.0
    topics: List[str] = Field(default_factory=list)


class SizingRecommendation(BaseModel):
    resource_type: str = ""
    recommended_shape: str = ""
    vcpus: int = 0
    memory_gb: float = 0.0
    storage_gb: float = 0.0
    rationale: str = ""


class PricingEstimate(BaseModel):
    resource_name: str = ""
    monthly_cost_usd: float = 0.0
    annual_cost_usd: float = 0.0
    cost_breakdown: Dict[str, float] = Field(default_factory=dict)


class AnalysisState(BaseModel):
    current_state: Dict[str, Any] = Field(default_factory=dict)
    requirements: Dict[str, Any] = Field(default_factory=dict)
    service_mappings: List[OCIServiceMapping] = Field(default_factory=list)
    archhub_references: List[ArchHubReference] = Field(default_factory=list)
    livelabs_workshops: List[LiveLabsWorkshop] = Field(default_factory=list)
    sizing_recommendations: List[SizingRecommendation] = Field(default_factory=list)
    pricing_estimates: List[PricingEstimate] = Field(default_factory=list)
    total_monthly_cost_usd: float = 0.0
    total_annual_cost_usd: float = 0.0
    target_design: Dict[str, Any] = Field(default_factory=dict)
    savings_analysis: Dict[str, Any] = Field(default_factory=dict)
    kb_intelligence: Dict[str, Any] = Field(default_factory=dict)


# Phase 3: Design Models
class ArchitectureComponent(BaseModel):
    component_id: str = ""
    component_type: str = ""
    name: str = ""
    oci_service: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    deployment_order: int = 0
    state: str = "pending"


class DesignDiagram(BaseModel):
    diagram_type: Literal["logical", "sequence", "gantt", "network", "swimlane"] = "logical"
    diagram_data: str = ""
    format: Literal["png", "svg", "mermaid", "graphviz"] = "mermaid"


class DesignState(BaseModel):
    architecture_components: List[ArchitectureComponent] = Field(default_factory=list)
    component_dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    deployment_sequence: List[str] = Field(default_factory=list)
    diagrams: List[DesignDiagram] = Field(default_factory=list)
    design_validated: bool = False
    design_architecture_json: str = ""
    design_summary: str = ""
    design_component_count: int = 0
    design_validation_results: Dict[str, Any] = Field(default_factory=dict)
    design_build_plan: List[str] = Field(default_factory=list)
    design_status: str = "not_started"
    kb_intelligence: Dict[str, Any] = Field(default_factory=dict)


# Phase 4: Review Models
class ReviewFeedback(BaseModel):
    component_id: Optional[str] = None
    feedback_type: Literal["change_request", "question", "concern", "approval"] = "concern"
    description: str = ""
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    resolved: bool = False


class ReviewState(BaseModel):
    feedback_items: List[ReviewFeedback] = Field(default_factory=list)
    review_iterations: int = 0
    approval_score: float = 0.0
    final_approved: bool = False
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    kb_intelligence: Dict[str, Any] = Field(default_factory=dict)


# Phase 5: Implementation Models
class TerraformModule(BaseModel):
    module_name: str = ""
    source: str = ""
    version: str = ""
    variables: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)


class GeneratedCode(BaseModel):
    file_path: str = ""
    content: str = ""
    module_type: str = ""
    validated: bool = False
    validation_errors: List[str] = Field(default_factory=list)


class ImplementationState(BaseModel):
    strategy: Optional[ImplementationStrategy] = None
    terraform_modules: List[TerraformModule] = Field(default_factory=list)
    generated_code: List[GeneratedCode] = Field(default_factory=list)
    code_validated: bool = False
    project_exported: bool = False
    export_path: Optional[str] = None
    selected_component: Optional[Dict[str, Any]] = None
    framework_artifacts: Optional[Dict[str, Any]] = None
    import_path: Optional[str] = None
    import_validated: bool = False
    kb_intelligence: Dict[str, Any] = Field(default_factory=dict)


# Phase 6: Deployment Models
class ValidationResult(BaseModel):
    check_name: str = ""
    passed: bool = False
    details: str = ""
    severity: Literal["info", "warning", "error"] = "info"


class DeploymentJob(BaseModel):
    job_id: str = ""
    status: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    logs: List[str] = Field(default_factory=list)


class DeploymentState(BaseModel):
    stack_id: Optional[str] = None
    stack_name: Optional[str] = None
    pre_validation_results: List[ValidationResult] = Field(default_factory=list)
    terraform_plan: Optional[str] = None
    plan_approved: bool = False
    deployment_jobs: List[DeploymentJob] = Field(default_factory=list)
    post_validation_results: List[ValidationResult] = Field(default_factory=list)
    deployment_successful: bool = False
    deployment_report_path: Optional[str] = None
    deployment_artifacts: Dict[str, Any] = Field(default_factory=dict)
    deployment_status: str = "not_started"
    kb_intelligence: Dict[str, Any] = Field(default_factory=dict)


# On-Demand Feature Models
class RiskItem(BaseModel):
    category: str = ""
    risk_name: str = ""
    description: str = ""
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    probability: Literal["low", "medium", "high"] = "medium"
    impact: Literal["low", "medium", "high"] = "medium"
    mitigation: str = ""
    risk_score: float = 0.0


class CostOptimization(BaseModel):
    optimization_type: str = ""
    description: str = ""
    potential_savings_pct: float = 0.0
    potential_savings_usd: float = 0.0
    effort: Literal["low", "medium", "high"] = "medium"
    risk_level: Literal["low", "medium", "high"] = "low"


class OnDemandState(BaseModel):
    risk_analysis: List[RiskItem] = Field(default_factory=list)
    overall_risk_score: float = 0.0
    cost_optimizations: List[CostOptimization] = Field(default_factory=list)
    total_potential_savings_usd: float = 0.0
    kb_query_history: List[Dict[str, Any]] = Field(default_factory=list)
    mcp_health: Dict[str, Any] = Field(default_factory=dict)


# Main Migration State
class MigrationState(BaseModel):
    # Metadata
    migration_id: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    current_phase: str = "discovery"
    phase_status: PhaseStatus = PhaseStatus.PENDING

    # Input Context
    user_context: str = ""
    uploaded_documents: List[str] = Field(default_factory=list)
    bom_file: Optional[str] = None
    source_provider: str = ""
    target_region: str = "us-ashburn-1"

    # Phase States
    discovery: DiscoveryState = Field(default_factory=DiscoveryState)
    analysis: AnalysisState = Field(default_factory=AnalysisState)
    design: DesignState = Field(default_factory=DesignState)
    review: ReviewState = Field(default_factory=ReviewState)
    implementation: ImplementationState = Field(default_factory=ImplementationState)
    deployment: DeploymentState = Field(default_factory=DeploymentState)
    on_demand: OnDemandState = Field(default_factory=OnDemandState)

    # Review Gates
    discovery_review_decision: Optional[ReviewDecision] = None
    discovery_review_feedback: str = ""
    discovery_review_status: str = "pending"
    archhub_review_decision: Optional[ReviewDecision] = None
    archhub_review_feedback: str = ""
    archhub_review_status: str = "pending"
    livelabs_review_decision: Optional[ReviewDecision] = None
    livelabs_review_feedback: str = ""
    livelabs_review_status: str = "pending"
    design_review_decision: Optional[ReviewDecision] = None
    design_review_feedback: str = ""
    design_review_status: str = "pending"
    review_status: str = "pending"
    review_feedback: str = ""
    code_review_decision: Optional[ReviewDecision] = None
    code_review_feedback: str = ""
    import_review_decision: Optional[ReviewDecision] = None
    import_review_feedback: str = ""
    implementation_review_decision: Optional[ReviewDecision] = None
    implementation_review_feedback: str = ""
    pre_deployment_review_decision: Optional[ReviewDecision] = None
    pre_deployment_review_feedback: str = ""
    plan_review_decision: Optional[ReviewDecision] = None
    plan_review_feedback: str = ""

    # Messages and Errors
    messages: List[Dict[str, str]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    # Feature Flags
    risk_analysis_requested: bool = False
    cost_optimization_requested: bool = False

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


def create_migration_state(
    migration_id: str,
    user_context: str,
    source_provider: str,
    target_region: str = "us-ashburn-1"
) -> MigrationState:
    return MigrationState(
        migration_id=migration_id,
        user_context=user_context,
        source_provider=source_provider,
        target_region=target_region
    )
