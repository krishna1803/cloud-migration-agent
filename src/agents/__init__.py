"""Agents package initialization"""

from src.agents.phase1_discovery import (
    intake_plan,
    kb_enrich_discovery,
    document_ingestion,
    bom_analysis,
    extract_evidence,
    gap_detection,
    clarifications_needed,
    should_request_clarifications
)

from src.agents.phase2_analysis import (
    reconstruct_current_state,
    service_mapping,
    archhub_discovery,
    livelabs_discovery,
    target_design,
    resource_sizing,
    cost_estimation
)

from src.agents.phase3_design import (
    formal_architecture_modeling,
    component_definition,
    dependency_mapping,
    topological_sort_deployment,
    diagram_generation,
    design_phase_complete
)

from src.agents.phase4_review import (
    final_validation,
    compliance_check,
    risk_assessment,
    cost_verification,
    feedback_incorporation,
    approval_check,
    should_iterate_review
)

from src.agents.phase5_implementation import (
    strategy_selection,
    terraform_module_definition,
    terraform_code_generation,
    code_validation,
    project_export
)

from src.agents.phase6_deployment import (
    pre_deployment_validation,
    create_rm_stack,
    generate_terraform_plan,
    execute_deployment,
    monitor_deployment,
    post_deployment_validation,
    generate_deployment_report,
    deployment_complete
)

from src.agents.review_gates import (
    discovery_review_gate,
    process_discovery_review,
    archhub_review_gate,
    process_archhub_review,
    livelabs_review_gate,
    process_livelabs_review,
    design_review_gate,
    process_design_review,
    code_review_gate,
    process_code_review,
    plan_review_gate,
    process_plan_review,
    is_review_approved
)

from src.agents.workflow import (
    create_migration_workflow,
    execute_workflow_until_interrupt,
    resume_workflow_after_review,
    migration_workflow
)

__all__ = [
    # Phase 1
    "intake_plan",
    "kb_enrich_discovery",
    "document_ingestion",
    "bom_analysis",
    "extract_evidence",
    "gap_detection",
    "clarifications_needed",
    "should_request_clarifications",
    
    # Phase 2
    "reconstruct_current_state",
    "service_mapping",
    "archhub_discovery",
    "livelabs_discovery",
    "target_design",
    "resource_sizing",
    "cost_estimation",
    
    # Phase 3
    "formal_architecture_modeling",
    "component_definition",
    "dependency_mapping",
    "topological_sort_deployment",
    "diagram_generation",
    "design_phase_complete",
    
    # Phase 4
    "final_validation",
    "compliance_check",
    "risk_assessment",
    "cost_verification",
    "feedback_incorporation",
    "approval_check",
    "should_iterate_review",
    
    # Phase 5
    "strategy_selection",
    "terraform_module_definition",
    "terraform_code_generation",
    "code_validation",
    "project_export",
    
    # Phase 6
    "pre_deployment_validation",
    "create_rm_stack",
    "generate_terraform_plan",
    "execute_deployment",
    "monitor_deployment",
    "post_deployment_validation",
    "generate_deployment_report",
    "deployment_complete",
    
    # Review Gates
    "discovery_review_gate",
    "process_discovery_review",
    "archhub_review_gate",
    "process_archhub_review",
    "livelabs_review_gate",
    "process_livelabs_review",
    "design_review_gate",
    "process_design_review",
    "code_review_gate",
    "process_code_review",
    "plan_review_gate",
    "process_plan_review",
    "is_review_approved",
    
    # Workflow
    "create_migration_workflow",
    "execute_workflow_until_interrupt",
    "resume_workflow_after_review",
    "migration_workflow"
]
