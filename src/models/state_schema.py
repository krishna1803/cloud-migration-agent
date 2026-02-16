"""
State schema for the Cloud Migration Agent Platform.

Defines the complete state structure that flows through all 6 phases
of the migration workflow.
"""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class PhaseStatus(str, Enum):
    """Phase execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(str, Enum):
    """Review gate decisions"""
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class ImplementationStrategy(str, Enum):
    """Implementation pathway options"""
    PRE_PACKAGED = "pre_packaged"
    DYNAMIC_TERRAFORM = "dynamic_terraform"
    THIRD_PARTY = "third_party"


# Phase 1: Discovery Models
class DiscoveredService(BaseModel):
    """Discovered cloud service"""
    service_name: str
    provider: str  # AWS, Azure, GCP, On-Prem
    resource_type: str
    configuration: Dict[str, Any]
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NetworkArchitecture(BaseModel):
    """Network topology"""
    vpcs: List[Dict[str, Any]] = Field(default_factory=list)
    subnets: List[Dict[str, Any]] = Field(default_factory=list)
    security_groups: List[Dict[str, Any]] = Field(default_factory=list)
    route_tables: List[Dict[str, Any]] = Field(default_factory=list)
    load_balancers: List[Dict[str, Any]] = Field(default_factory=list)


class ComputeResource(BaseModel):
    """Compute instance details"""
    instance_id: str
    instance_type: str
    vcpus: int
    memory_gb: float
    storage_gb: float
    os: str
    tags: Dict[str, str] = Field(default_factory=dict)


class StorageResource(BaseModel):
    """Storage resource details"""
    resource_id: str
    storage_type: str  # S3, EBS, RDS, etc.
    size_gb: float
    iops: Optional[int] = None
    throughput_mbps: Optional[int] = None


class SecurityPosture(BaseModel):
    """Security configuration"""
    iam_roles: List[Dict[str, Any]] = Field(default_factory=list)
    policies: List[Dict[str, Any]] = Field(default_factory=list)
    encryption: Dict[str, Any] = Field(default_factory=dict)
    compliance_requirements: List[str] = Field(default_factory=list)


class Gap(BaseModel):
    """Missing or ambiguous information"""
    category: str
    description: str
    severity: Literal["low", "medium", "high"]
    clarification_question: str


class DiscoveryState(BaseModel):
    """Phase 1: Discovery state"""
    discovered_services: List[DiscoveredService] = Field(default_factory=list)
    network_architecture: Optional[NetworkArchitecture] = None
    compute_resources: List[ComputeResource] = Field(default_factory=list)
    storage_resources: List[StorageResource] = Field(default_factory=list)
    security_posture: Optional[SecurityPosture] = None
    gaps_identified: List[Gap] = Field(default_factory=list)
    discovery_confidence: float = 0.0
    clarifications_requested: List[str] = Field(default_factory=list)
    clarifications_received: Dict[str, str] = Field(default_factory=dict)


# Phase 2: Analysis Models
class OCIServiceMapping(BaseModel):
    """Source to OCI service mapping"""
    source_service: str
    oci_service: str
    mapping_confidence: float
    alternatives: List[str] = Field(default_factory=list)
    reasoning: str = ""


class ArchHubReference(BaseModel):
    """ArchHub reference architecture"""
    architecture_id: str
    title: str
    description: str
    diagram_url: str
    components: List[str]
    match_score: float


class LiveLabsWorkshop(BaseModel):
    """LiveLabs workshop recommendation"""
    workshop_id: str
    title: str
    description: str
    url: str
    relevance_score: float
    topics: List[str]


class SizingRecommendation(BaseModel):
    """Resource sizing recommendation"""
    resource_type: str
    recommended_shape: str
    vcpus: int
    memory_gb: float
    storage_gb: float
    rationale: str


class PricingEstimate(BaseModel):
    """Cost estimation"""
    resource_name: str
    monthly_cost_usd: float
    annual_cost_usd: float
    cost_breakdown: Dict[str, float]


class AnalysisState(BaseModel):
    """Phase 2: Analysis state"""
    service_mappings: List[OCIServiceMapping] = Field(default_factory=list)
    archhub_references: List[ArchHubReference] = Field(default_factory=list)
    livelabs_workshops: List[LiveLabsWorkshop] = Field(default_factory=list)
    sizing_recommendations: List[SizingRecommendation] = Field(default_factory=list)
    pricing_estimates: List[PricingEstimate] = Field(default_factory=list)
    total_monthly_cost_usd: float = 0.0
    total_annual_cost_usd: float = 0.0


# Phase 3: Design Models
class ArchitectureComponent(BaseModel):
    """Architecture component in design"""
    component_id: str
    component_type: str
    name: str
    oci_service: str
    configuration: Dict[str, Any]
    dependencies: List[str] = Field(default_factory=list)
    deployment_order: int = 0


class DesignDiagram(BaseModel):
    """Architecture diagram"""
    diagram_type: Literal["logical", "sequence", "gantt", "network"]
    diagram_data: str  # Base64 encoded image or mermaid/graphviz code
    format: Literal["png", "svg", "mermaid", "graphviz"]


class DesignState(BaseModel):
    """Phase 3: Design state"""
    architecture_components: List[ArchitectureComponent] = Field(default_factory=list)
    component_dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    deployment_sequence: List[str] = Field(default_factory=list)  # Topologically sorted
    diagrams: List[DesignDiagram] = Field(default_factory=list)
    design_validated: bool = False


# Phase 4: Review Models
class ReviewFeedback(BaseModel):
    """Review feedback item"""
    component_id: Optional[str] = None
    feedback_type: Literal["change_request", "question", "concern", "approval"]
    description: str
    priority: Literal["low", "medium", "high"]
    resolved: bool = False


class ReviewState(BaseModel):
    """Phase 4: Review state"""
    feedback_items: List[ReviewFeedback] = Field(default_factory=list)
    review_iterations: int = 0
    approval_score: float = 0.0
    final_approved: bool = False


# Phase 5: Implementation Models
class TerraformModule(BaseModel):
    """Terraform module"""
    module_name: str
    source: str
    version: str
    variables: Dict[str, Any]
    outputs: Dict[str, Any] = Field(default_factory=dict)


class GeneratedCode(BaseModel):
    """Generated Terraform code"""
    file_path: str
    content: str
    module_type: str
    validated: bool = False
    validation_errors: List[str] = Field(default_factory=list)


class ImplementationState(BaseModel):
    """Phase 5: Implementation state"""
    strategy: Optional[ImplementationStrategy] = None
    terraform_modules: List[TerraformModule] = Field(default_factory=list)
    generated_code: List[GeneratedCode] = Field(default_factory=list)
    code_validated: bool = False
    project_exported: bool = False
    export_path: Optional[str] = None


# Phase 6: Deployment Models
class ValidationResult(BaseModel):
    """Validation check result"""
    check_name: str
    passed: bool
    details: str
    severity: Literal["info", "warning", "error"]


class DeploymentJob(BaseModel):
    """OCI RM deployment job"""
    job_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    logs: List[str] = Field(default_factory=list)


class DeploymentState(BaseModel):
    """Phase 6: Deployment state"""
    stack_id: Optional[str] = None
    stack_name: Optional[str] = None
    pre_validation_results: List[ValidationResult] = Field(default_factory=list)
    terraform_plan: Optional[str] = None
    plan_approved: bool = False
    deployment_jobs: List[DeploymentJob] = Field(default_factory=list)
    post_validation_results: List[ValidationResult] = Field(default_factory=list)
    deployment_successful: bool = False
    deployment_report_path: Optional[str] = None


# Main Migration State
class MigrationState(BaseModel):
    """Complete migration workflow state"""
    
    # Metadata
    migration_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    current_phase: str = "discovery"
    phase_status: PhaseStatus = PhaseStatus.PENDING
    
    # Input Context
    user_context: str = ""
    uploaded_documents: List[str] = Field(default_factory=list)
    bom_file: Optional[str] = None
    source_provider: str = ""  # AWS, Azure, GCP, On-Prem
    target_region: str = "us-ashburn-1"
    
    # Phase States
    discovery: DiscoveryState = Field(default_factory=DiscoveryState)
    analysis: AnalysisState = Field(default_factory=AnalysisState)
    design: DesignState = Field(default_factory=DesignState)
    review: ReviewState = Field(default_factory=ReviewState)
    implementation: ImplementationState = Field(default_factory=ImplementationState)
    deployment: DeploymentState = Field(default_factory=DeploymentState)
    
    # Review Gates
    discovery_review_decision: Optional[ReviewDecision] = None
    discovery_review_feedback: str = ""
    archhub_review_decision: Optional[ReviewDecision] = None
    archhub_review_feedback: str = ""
    livelabs_review_decision: Optional[ReviewDecision] = None
    livelabs_review_feedback: str = ""
    design_review_decision: Optional[ReviewDecision] = None
    design_review_feedback: str = ""
    code_review_decision: Optional[ReviewDecision] = None
    code_review_feedback: str = ""
    plan_review_decision: Optional[ReviewDecision] = None
    plan_review_feedback: str = ""
    
    # Messages and Errors
    messages: List[Dict[str, str]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    
    # Feature Flags (for on-demand features)
    risk_analysis_requested: bool = False
    cost_optimization_requested: bool = False
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Helper function to create a new migration state
def create_migration_state(
    migration_id: str,
    user_context: str,
    source_provider: str,
    target_region: str = "us-ashburn-1"
) -> MigrationState:
    """Create a new migration state with initial values"""
    return MigrationState(
        migration_id=migration_id,
        user_context=user_context,
        source_provider=source_provider,
        target_region=target_region
    )
