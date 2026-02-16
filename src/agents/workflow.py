"""
LangGraph workflow orchestrator for the Cloud Migration Agent.

Defines the complete 6-phase workflow with all nodes and edges.
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Any

from src.models.state_schema import MigrationState, PhaseStatus, ReviewDecision
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
from src.agents.review_gates import (
    discovery_review_gate,
    archhub_review_gate,
    livelabs_review_gate,
    design_review_gate,
    code_review_gate,
    plan_review_gate
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
from src.utils.checkpoint import checkpoint_saver
from src.utils.logger import logger


def create_migration_workflow() -> StateGraph:
    """
    Create the complete migration workflow graph.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    
    # Create workflow graph
    workflow = StateGraph(MigrationState)
    
    # ========== PHASE 1: DISCOVERY ==========
    workflow.add_node("intake_plan", intake_plan)
    workflow.add_node("kb_enrich_discovery", kb_enrich_discovery)
    workflow.add_node("document_ingestion", document_ingestion)
    workflow.add_node("bom_analysis", bom_analysis)
    workflow.add_node("extract_evidence", extract_evidence)
    workflow.add_node("gap_detection", gap_detection)
    workflow.add_node("clarifications_needed", clarifications_needed)
    
    # Phase 1 edges
    workflow.set_entry_point("intake_plan")
    workflow.add_edge("intake_plan", "kb_enrich_discovery")
    workflow.add_edge("kb_enrich_discovery", "document_ingestion")
    workflow.add_edge("document_ingestion", "bom_analysis")
    workflow.add_edge("bom_analysis", "extract_evidence")
    workflow.add_edge("extract_evidence", "gap_detection")
    
    # Conditional edge: clarify or continue
    workflow.add_conditional_edges(
        "gap_detection",
        should_request_clarifications,
        {
            "clarify": "clarifications_needed",
            "continue": "discovery_review_gate"
        }
    )
    
    # Clarifications loop back
    workflow.add_edge("clarifications_needed", "extract_evidence")
    
    # ========== PHASE 1.5: DISCOVERY REVIEW GATE ==========
    workflow.add_node("discovery_review_gate", discovery_review_gate)
    
    # After discovery review, proceed to analysis
    workflow.add_edge("discovery_review_gate", "reconstruct_current_state")
    
    # ========== PHASE 2: ANALYSIS ==========
    workflow.add_node("reconstruct_current_state", reconstruct_current_state)
    workflow.add_node("service_mapping", service_mapping)
    workflow.add_node("archhub_discovery", archhub_discovery)
    workflow.add_node("livelabs_discovery", livelabs_discovery)
    workflow.add_node("target_design", target_design)
    workflow.add_node("resource_sizing", resource_sizing)
    workflow.add_node("cost_estimation", cost_estimation)
    
    # Phase 2 edges
    workflow.add_edge("reconstruct_current_state", "service_mapping")
    workflow.add_edge("service_mapping", "archhub_discovery")
    workflow.add_edge("archhub_discovery", "archhub_review_gate")
    
    # ========== PHASE 2.5a: ARCHHUB REVIEW GATE ==========
    workflow.add_node("archhub_review_gate", archhub_review_gate)
    workflow.add_edge("archhub_review_gate", "livelabs_discovery")
    
    # ========== PHASE 2.5b: LIVELABS REVIEW GATE ==========
    workflow.add_node("livelabs_review_gate", livelabs_review_gate)
    workflow.add_edge("livelabs_review_gate", "target_design")
    
    # Continue analysis
    workflow.add_edge("target_design", "resource_sizing")
    workflow.add_edge("resource_sizing", "cost_estimation")
    workflow.add_edge("cost_estimation", "design_phase_start")
    
    # ========== PHASE 3: DESIGN ==========
    workflow.add_node("formal_architecture_modeling", formal_architecture_modeling)
    workflow.add_node("component_definition", component_definition)
    workflow.add_node("dependency_mapping", dependency_mapping)
    workflow.add_node("topological_sort_deployment", topological_sort_deployment)
    workflow.add_node("diagram_generation", diagram_generation)
    workflow.add_node("design_phase_complete", design_phase_complete)
    
    workflow.add_edge("cost_estimation", "formal_architecture_modeling")
    workflow.add_edge("formal_architecture_modeling", "component_definition")
    workflow.add_edge("component_definition", "dependency_mapping")
    workflow.add_edge("dependency_mapping", "topological_sort_deployment")
    workflow.add_edge("topological_sort_deployment", "diagram_generation")
    workflow.add_edge("diagram_generation", "design_phase_complete")
    workflow.add_edge("design_phase_complete", "design_review_gate")
    
    # ========== PHASE 3.5: DESIGN REVIEW GATE ==========
    workflow.add_node("design_review_gate", design_review_gate)
    workflow.add_edge("design_review_gate", "review_phase_start")
    
    # ========== PHASE 4: REVIEW ==========
    workflow.add_node("final_validation", final_validation)
    workflow.add_node("compliance_check", compliance_check)
    workflow.add_node("risk_assessment", risk_assessment)
    workflow.add_node("cost_verification", cost_verification)
    workflow.add_node("feedback_incorporation", feedback_incorporation)
    workflow.add_node("approval_check", approval_check)
    
    workflow.add_edge("design_review_gate", "final_validation")
    workflow.add_edge("final_validation", "compliance_check")
    workflow.add_edge("compliance_check", "risk_assessment")
    workflow.add_edge("risk_assessment", "cost_verification")
    workflow.add_edge("cost_verification", "feedback_incorporation")
    workflow.add_edge("feedback_incorporation", "approval_check")
    
    # Conditional: iterate review or proceed
    workflow.add_conditional_edges(
        "approval_check",
        should_iterate_review,
        {
            "iterate": "final_validation",
            "proceed": "strategy_selection"
        }
    )
    
    # ========== PHASE 5: IMPLEMENTATION ==========
    workflow.add_node("strategy_selection", strategy_selection)
    workflow.add_node("terraform_module_definition", terraform_module_definition)
    workflow.add_node("terraform_code_generation", terraform_code_generation)
    workflow.add_node("code_validation", code_validation)
    workflow.add_node("project_export", project_export)
    
    workflow.add_edge("strategy_selection", "terraform_module_definition")
    workflow.add_edge("terraform_module_definition", "terraform_code_generation")
    workflow.add_edge("terraform_code_generation", "code_validation")
    workflow.add_edge("code_validation", "project_export")
    workflow.add_edge("project_export", "code_review_gate")
    
    # ========== PHASE 5.5: CODE REVIEW GATE ==========
    workflow.add_node("code_review_gate", code_review_gate)
    workflow.add_edge("code_review_gate", "deployment_phase_start")
    
    # ========== PHASE 6: DEPLOYMENT ==========
    workflow.add_node("pre_deployment_validation", pre_deployment_validation)
    workflow.add_node("create_rm_stack", create_rm_stack)
    workflow.add_node("generate_terraform_plan", generate_terraform_plan)
    workflow.add_node("execute_deployment", execute_deployment)
    workflow.add_node("monitor_deployment", monitor_deployment)
    workflow.add_node("post_deployment_validation", post_deployment_validation)
    workflow.add_node("generate_deployment_report", generate_deployment_report)
    workflow.add_node("deployment_complete", deployment_complete)
    
    workflow.add_edge("code_review_gate", "pre_deployment_validation")
    workflow.add_edge("pre_deployment_validation", "create_rm_stack")
    workflow.add_edge("create_rm_stack", "generate_terraform_plan")
    workflow.add_edge("generate_terraform_plan", "plan_review_gate")
    
    # ========== PHASE 6.5: PLAN REVIEW GATE ==========
    workflow.add_node("plan_review_gate", plan_review_gate)
    workflow.add_edge("plan_review_gate", "execute_deployment")
    workflow.add_edge("execute_deployment", "monitor_deployment")
    workflow.add_edge("monitor_deployment", "post_deployment_validation")
    workflow.add_edge("post_deployment_validation", "generate_deployment_report")
    workflow.add_edge("generate_deployment_report", "deployment_complete")
    workflow.add_edge("deployment_complete", END)
    
    # Compile workflow with checkpointing
    compiled_workflow = workflow.compile(
        checkpointer=checkpoint_saver,
        interrupt_before=[
            "discovery_review_gate",
            "archhub_review_gate",
            "livelabs_review_gate",
            "design_review_gate",
            "code_review_gate",
            "plan_review_gate"
        ]
    )
    
    logger.info("Migration workflow compiled successfully")
    
    return compiled_workflow


# Workflow execution helpers
async def execute_workflow_until_interrupt(
    workflow: StateGraph,
    initial_state: MigrationState,
    migration_id: str
) -> MigrationState:
    """
    Execute workflow until it reaches a human review gate.
    
    Args:
        workflow: Compiled workflow graph
        initial_state: Initial migration state
        migration_id: Migration ID for checkpointing
        
    Returns:
        State at the interruption point
    """
    config = {"configurable": {"migration_id": migration_id}}
    
    # Run workflow
    result = await workflow.ainvoke(initial_state, config=config)
    
    logger.info(f"Workflow interrupted at phase: {result.current_phase}")
    
    return result


async def resume_workflow_after_review(
    workflow: StateGraph,
    migration_id: str,
    review_decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """
    Resume workflow after human review.
    
    Args:
        workflow: Compiled workflow graph
        migration_id: Migration ID
        review_decision: Review decision (approve/request_changes/reject)
        feedback: Optional feedback text
        
    Returns:
        Updated state after resuming
    """
    config = {"configurable": {"migration_id": migration_id}}
    
    # Get current state
    from src.utils.checkpoint import checkpoint_saver
    state = checkpoint_saver.get_migration_state(migration_id)
    
    if not state:
        raise ValueError(f"Migration {migration_id} not found")
    
    # Process review decision based on current phase
    current_phase = state.current_phase
    
    if "discovery_review" in current_phase:
        from src.agents.review_gates import process_discovery_review
        state = process_discovery_review(state, review_decision, feedback)
    elif "archhub" in current_phase:
        from src.agents.review_gates import process_archhub_review
        state = process_archhub_review(state, review_decision, feedback)
    elif "livelabs" in current_phase:
        from src.agents.review_gates import process_livelabs_review
        state = process_livelabs_review(state, review_decision, feedback)
    elif "design_review" in current_phase:
        from src.agents.review_gates import process_design_review
        state = process_design_review(state, review_decision, feedback)
    elif "code_review" in current_phase:
        from src.agents.review_gates import process_code_review
        state = process_code_review(state, review_decision, feedback)
    elif "plan_review" in current_phase:
        from src.agents.review_gates import process_plan_review
        state = process_plan_review(state, review_decision, feedback)
    
    # Save updated state
    checkpoint_saver.save_migration_state(migration_id, state, "review_processed")
    
    # Resume workflow if approved
    if review_decision == ReviewDecision.APPROVE:
        result = await workflow.ainvoke(state, config=config)
        return result
    
    return state


# Global workflow instance
migration_workflow = create_migration_workflow()
