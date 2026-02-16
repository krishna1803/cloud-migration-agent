"""
Review Gate nodes for human-in-the-loop validation.

Implements all review gates across the 6-phase workflow.
"""

from src.models.state_schema import MigrationState, PhaseStatus, ReviewDecision
from src.utils.logger import logger, log_review_gate


# Phase 1.5: Discovery Review Gate
def discovery_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of discovered architecture.
    
    This node pauses the workflow until user provides review decision.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with review status
    """
    try:
        logger.info(f"Discovery review gate for migration {state.migration_id}")
        
        # Set status to waiting for review
        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "discovery_review"
        
        # Log the gate
        log_review_gate(
            state.migration_id,
            "discovery_review",
            "pending"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Discovery review gate error: {str(e)}")
        state.errors.append(f"Discovery review error: {str(e)}")
        return state


def process_discovery_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """
    Process discovery review decision.
    
    Args:
        state: Current migration state
        decision: Review decision (approve/request_changes/reject)
        feedback: Optional feedback text
        
    Returns:
        Updated state with decision processed
    """
    state.discovery_review_decision = decision
    state.discovery_review_feedback = feedback
    
    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.current_phase = "analysis"
        log_review_gate(state.migration_id, "discovery_review", "approved")
        
    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        # Loop back to evidence extraction with feedback
        log_review_gate(state.migration_id, "discovery_review", "changes_requested")
        
    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "discovery_review", "rejected")
    
    return state


# Phase 2.5a: ArchHub Review Gate
def archhub_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of ArchHub reference architectures.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state waiting for review
    """
    try:
        logger.info(f"ArchHub review gate for migration {state.migration_id}")
        
        state.phase_status = PhaseStatus.WAITING_REVIEW
        
        log_review_gate(
            state.migration_id,
            "archhub_review",
            "pending"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"ArchHub review gate error: {str(e)}")
        state.errors.append(f"ArchHub review error: {str(e)}")
        return state


def process_archhub_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """Process ArchHub review decision"""
    state.archhub_review_decision = decision
    state.archhub_review_feedback = feedback
    
    if decision == ReviewDecision.APPROVE:
        log_review_gate(state.migration_id, "archhub_review", "approved")
    elif decision == ReviewDecision.REQUEST_CHANGES:
        log_review_gate(state.migration_id, "archhub_review", "changes_requested")
    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "archhub_review", "rejected")
    
    return state


# Phase 2.5b: LiveLabs Review Gate
def livelabs_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of LiveLabs workshop recommendations.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state waiting for review
    """
    try:
        logger.info(f"LiveLabs review gate for migration {state.migration_id}")
        
        state.phase_status = PhaseStatus.WAITING_REVIEW
        
        log_review_gate(
            state.migration_id,
            "livelabs_review",
            "pending"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"LiveLabs review gate error: {str(e)}")
        state.errors.append(f"LiveLabs review error: {str(e)}")
        return state


def process_livelabs_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """Process LiveLabs review decision"""
    state.livelabs_review_decision = decision
    state.livelabs_review_feedback = feedback
    
    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.IN_PROGRESS
        log_review_gate(state.migration_id, "livelabs_review", "approved")
    elif decision == ReviewDecision.REQUEST_CHANGES:
        log_review_gate(state.migration_id, "livelabs_review", "changes_requested")
    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "livelabs_review", "rejected")
    
    return state


# Phase 3.5: Design Review Gate
def design_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of formal architecture design.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state waiting for review
    """
    try:
        logger.info(f"Design review gate for migration {state.migration_id}")
        
        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "design_review"
        
        log_review_gate(
            state.migration_id,
            "design_review",
            "pending"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Design review gate error: {str(e)}")
        state.errors.append(f"Design review error: {str(e)}")
        return state


def process_design_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """Process design review decision"""
    state.design_review_decision = decision
    state.design_review_feedback = feedback
    
    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.current_phase = "review"
        state.design.design_validated = True
        log_review_gate(state.migration_id, "design_review", "approved")
        
    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        # Loop back to design phase
        log_review_gate(state.migration_id, "design_review", "changes_requested")
        
    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "design_review", "rejected")
    
    return state


# Phase 5.5: Code Review Gate
def code_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of generated Terraform code.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state waiting for review
    """
    try:
        logger.info(f"Code review gate for migration {state.migration_id}")
        
        state.phase_status = PhaseStatus.WAITING_REVIEW
        
        log_review_gate(
            state.migration_id,
            "code_review",
            "pending"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Code review gate error: {str(e)}")
        state.errors.append(f"Code review error: {str(e)}")
        return state


def process_code_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """Process code review decision"""
    state.code_review_decision = decision
    state.code_review_feedback = feedback
    
    if decision == ReviewDecision.APPROVE:
        state.implementation.code_validated = True
        state.current_phase = "deployment"
        log_review_gate(state.migration_id, "code_review", "approved")
        
    elif decision == ReviewDecision.REQUEST_CHANGES:
        # Loop back to code generation
        log_review_gate(state.migration_id, "code_review", "changes_requested")
        
    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "code_review", "rejected")
    
    return state


# Phase 6.5: Plan Review Gate
def plan_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of Terraform plan before deployment.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state waiting for review
    """
    try:
        logger.info(f"Plan review gate for migration {state.migration_id}")
        
        state.phase_status = PhaseStatus.WAITING_REVIEW
        
        log_review_gate(
            state.migration_id,
            "plan_review",
            "pending"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Plan review gate error: {str(e)}")
        state.errors.append(f"Plan review error: {str(e)}")
        return state


def process_plan_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """Process plan review decision"""
    state.plan_review_decision = decision
    state.plan_review_feedback = feedback
    
    if decision == ReviewDecision.APPROVE:
        state.deployment.plan_approved = True
        log_review_gate(state.migration_id, "plan_review", "approved")
        
    elif decision == ReviewDecision.REQUEST_CHANGES:
        # Need to regenerate code/plan
        log_review_gate(state.migration_id, "plan_review", "changes_requested")
        
    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "plan_review", "rejected")
    
    return state


# Helper function to check if review is approved
def is_review_approved(state: MigrationState, gate_name: str) -> bool:
    """
    Check if a review gate has been approved.
    
    Args:
        state: Current migration state
        gate_name: Name of the review gate
        
    Returns:
        True if approved, False otherwise
    """
    gate_decisions = {
        "discovery": state.discovery_review_decision,
        "archhub": state.archhub_review_decision,
        "livelabs": state.livelabs_review_decision,
        "design": state.design_review_decision,
        "code": state.code_review_decision,
        "plan": state.plan_review_decision
    }
    
    decision = gate_decisions.get(gate_name)
    return decision == ReviewDecision.APPROVE
