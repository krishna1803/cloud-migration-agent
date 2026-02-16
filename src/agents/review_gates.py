"""
Review Gate nodes for human-in-the-loop validation.

Implements all 10 review gates across the 6-phase migration workflow
per spec v4.0.0. Each gate has a gate function that pauses the workflow
and a process function that handles the user's review decision.

Gates:
    1. Discovery Review (Phase 1.5) - Review discovered architecture
    2. ArchHub Review (Phase 2) - Review ArchHub reference architectures
    3. LiveLabs Review (Phase 2) - Review LiveLabs workshop recommendations
    4. Design Review (Phase 3.5) - Review formal architecture design
    5. Review Phase Gate (Phase 4) - Review validation/compliance results
    6. Code Review (Phase 5) - Review generated Terraform code
    7. Import Review (Phase 5) - Review imported third-party artifacts
    8. Implementation Review (Phase 5) - Review full implementation package
    9. Pre-deployment Review (Phase 6) - Review pre-deployment validation
   10. Plan Review (Phase 6) - Review Terraform plan before apply
"""

from src.models.state_schema import MigrationState, PhaseStatus, ReviewDecision
from src.utils.logger import logger, log_review_gate


# ---------------------------------------------------------------------------
# Gate 1 - Phase 1.5: Discovery Review Gate
# ---------------------------------------------------------------------------

def discovery_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of discovered architecture.

    This node pauses the workflow until the user provides a review decision
    on the discovery results (services, network, compute, storage, gaps).

    Args:
        state: Current migration state after discovery phase completion.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Discovery review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "discovery_review"
        state.discovery_review_status = "waiting_review"

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
    Process the user's discovery review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded and phase advanced accordingly.
    """
    state.discovery_review_decision = decision
    state.discovery_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.current_phase = "analysis"
        state.discovery_review_status = "approved"
        log_review_gate(state.migration_id, "discovery_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.discovery_review_status = "changes_requested"
        # Loop back to evidence extraction with feedback
        log_review_gate(state.migration_id, "discovery_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        state.discovery_review_status = "rejected"
        log_review_gate(state.migration_id, "discovery_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 2 - Phase 2: ArchHub Review Gate
# ---------------------------------------------------------------------------

def archhub_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of ArchHub reference architectures.

    Pauses the workflow so the user can review the matched OCI reference
    architectures from ArchHub before they are used in subsequent design.

    Args:
        state: Current migration state with archhub_references populated.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"ArchHub review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "archhub_review"
        state.archhub_review_status = "waiting_review"

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
    """
    Process the user's ArchHub review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.archhub_review_decision = decision
    state.archhub_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.archhub_review_status = "approved"
        log_review_gate(state.migration_id, "archhub_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.archhub_review_status = "changes_requested"
        log_review_gate(state.migration_id, "archhub_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        state.archhub_review_status = "rejected"
        log_review_gate(state.migration_id, "archhub_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 3 - Phase 2: LiveLabs Review Gate
# ---------------------------------------------------------------------------

def livelabs_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of LiveLabs workshop recommendations.

    Pauses the workflow so the user can review the matched LiveLabs
    workshops that will be referenced in the migration guidance.

    Args:
        state: Current migration state with livelabs_workshops populated.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"LiveLabs review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "livelabs_review"
        state.livelabs_review_status = "waiting_review"

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
    """
    Process the user's LiveLabs review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.livelabs_review_decision = decision
    state.livelabs_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.livelabs_review_status = "approved"
        log_review_gate(state.migration_id, "livelabs_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.livelabs_review_status = "changes_requested"
        log_review_gate(state.migration_id, "livelabs_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        state.livelabs_review_status = "rejected"
        log_review_gate(state.migration_id, "livelabs_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 4 - Phase 3.5: Design Review Gate
# ---------------------------------------------------------------------------

def design_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of formal architecture design.

    Pauses the workflow so the user can review the generated OCI
    architecture design including components, dependencies, deployment
    sequence, and diagrams.

    Args:
        state: Current migration state with design phase completed.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Design review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "design_review"
        state.design_review_status = "waiting_review"

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
    """
    Process the user's design review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.design_review_decision = decision
    state.design_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.current_phase = "review"
        state.design_review_status = "approved"
        state.design.design_validated = True
        log_review_gate(state.migration_id, "design_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.design_review_status = "changes_requested"
        # Loop back to design phase for revisions
        log_review_gate(state.migration_id, "design_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        state.design_review_status = "rejected"
        log_review_gate(state.migration_id, "design_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 5 - Phase 4: Review Phase Gate
# ---------------------------------------------------------------------------

def review_phase_gate(state: MigrationState) -> MigrationState:
    """
    Human review of Phase 4 validation, compliance, and risk results.

    Pauses the workflow so the user can review the validation outcomes,
    compliance checks, risk assessment, and cost verification results
    produced during the review phase before advancing to implementation.

    Args:
        state: Current migration state with review phase completed.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Review phase gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "review_gate"
        state.review_status = "waiting_review"

        log_review_gate(
            state.migration_id,
            "review_phase",
            "pending"
        )

        return state

    except Exception as e:
        logger.error(f"Review phase gate error: {str(e)}")
        state.errors.append(f"Review phase gate error: {str(e)}")
        return state


def process_review_phase_gate(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """
    Process the user's review phase gate decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.current_phase = "implementation"
        state.review_status = "approved"
        state.review.final_approved = True
        log_review_gate(state.migration_id, "review_phase", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.review_status = "changes_requested"
        # Loop back to review phase for additional iterations
        state.review.review_iterations += 1
        log_review_gate(state.migration_id, "review_phase", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        state.review_status = "rejected"
        log_review_gate(state.migration_id, "review_phase", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 6 - Phase 5: Code Review Gate
# ---------------------------------------------------------------------------

def code_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of generated Terraform code.

    Pauses the workflow so the user can review the generated Terraform
    modules and configuration code before export/deployment.

    Args:
        state: Current migration state with code generation completed.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Code review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "code_review"

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
    """
    Process the user's code review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.code_review_decision = decision
    state.code_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.implementation.code_validated = True
        log_review_gate(state.migration_id, "code_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        # Loop back to code generation with feedback
        log_review_gate(state.migration_id, "code_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "code_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 7 - Phase 5: Import Review Gate
# ---------------------------------------------------------------------------

def import_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of imported third-party artifacts.

    Pauses the workflow so the user can review imported framework
    artifacts (e.g., pre-packaged Terraform modules from third-party
    sources) before they are integrated into the implementation.

    Args:
        state: Current migration state with import completed.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Import review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "import_review"

        log_review_gate(
            state.migration_id,
            "import_review",
            "pending"
        )

        return state

    except Exception as e:
        logger.error(f"Import review gate error: {str(e)}")
        state.errors.append(f"Import review error: {str(e)}")
        return state


def process_import_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """
    Process the user's import review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.import_review_decision = decision
    state.import_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.implementation.import_validated = True
        log_review_gate(state.migration_id, "import_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        # Loop back to re-import or adjust artifacts
        log_review_gate(state.migration_id, "import_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "import_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 8 - Phase 5: Implementation Review Gate
# ---------------------------------------------------------------------------

def implementation_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of the complete implementation package.

    Pauses the workflow so the user can review the full implementation
    package including all Terraform modules, generated code, and export
    artifacts before proceeding to deployment.

    Args:
        state: Current migration state with implementation completed.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Implementation review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "implementation_review"

        log_review_gate(
            state.migration_id,
            "implementation_review",
            "pending"
        )

        return state

    except Exception as e:
        logger.error(f"Implementation review gate error: {str(e)}")
        state.errors.append(f"Implementation review error: {str(e)}")
        return state


def process_implementation_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """
    Process the user's implementation review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.implementation_review_decision = decision
    state.implementation_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.current_phase = "deployment"
        state.implementation.project_exported = True
        log_review_gate(state.migration_id, "implementation_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        # Loop back to implementation phase
        log_review_gate(state.migration_id, "implementation_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "implementation_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 9 - Phase 6: Pre-deployment Review Gate
# ---------------------------------------------------------------------------

def pre_deployment_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of pre-deployment validation results.

    Pauses the workflow so the user can review the pre-deployment
    validation checks (OCI connectivity, quotas, permissions, network
    readiness) before the Terraform plan is generated.

    Args:
        state: Current migration state with pre-validation completed.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Pre-deployment review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "pre_deployment_review"

        log_review_gate(
            state.migration_id,
            "pre_deployment_review",
            "pending"
        )

        return state

    except Exception as e:
        logger.error(f"Pre-deployment review gate error: {str(e)}")
        state.errors.append(f"Pre-deployment review error: {str(e)}")
        return state


def process_pre_deployment_review(
    state: MigrationState,
    decision: ReviewDecision,
    feedback: str = ""
) -> MigrationState:
    """
    Process the user's pre-deployment review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.pre_deployment_review_decision = decision
    state.pre_deployment_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        log_review_gate(state.migration_id, "pre_deployment_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        # Loop back to fix pre-deployment issues
        log_review_gate(state.migration_id, "pre_deployment_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "pre_deployment_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Gate 10 - Phase 6: Plan Review Gate
# ---------------------------------------------------------------------------

def plan_review_gate(state: MigrationState) -> MigrationState:
    """
    Human review of Terraform plan before deployment.

    Pauses the workflow so the user can review the Terraform plan output
    (resources to be created, modified, or destroyed) before the actual
    apply step is executed via OCI Resource Manager.

    Args:
        state: Current migration state with terraform_plan populated.

    Returns:
        Updated state with phase_status set to WAITING_REVIEW.
    """
    try:
        logger.info(f"Plan review gate for migration {state.migration_id}")

        state.phase_status = PhaseStatus.WAITING_REVIEW
        state.current_phase = "plan_review"

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
    """
    Process the user's plan review decision.

    Args:
        state: Current migration state.
        decision: Review decision (approve / request_changes / reject).
        feedback: Optional feedback text from the reviewer.

    Returns:
        Updated state with the decision recorded.
    """
    state.plan_review_decision = decision
    state.plan_review_feedback = feedback

    if decision == ReviewDecision.APPROVE:
        state.phase_status = PhaseStatus.APPROVED
        state.deployment.plan_approved = True
        log_review_gate(state.migration_id, "plan_review", "approved")

    elif decision == ReviewDecision.REQUEST_CHANGES:
        state.phase_status = PhaseStatus.IN_PROGRESS
        # Need to regenerate code/plan
        log_review_gate(state.migration_id, "plan_review", "changes_requested")

    elif decision == ReviewDecision.REJECT:
        state.phase_status = PhaseStatus.REJECTED
        log_review_gate(state.migration_id, "plan_review", "rejected")

    return state


# ---------------------------------------------------------------------------
# Helper: Check Review Approval
# ---------------------------------------------------------------------------

def is_review_approved(state: MigrationState, gate_name: str) -> bool:
    """
    Check if a review gate has been approved.

    Provides a single lookup point for all 10 review gate decisions,
    useful for conditional routing in the LangGraph workflow.

    Args:
        state: Current migration state.
        gate_name: Name of the review gate. Valid names:
            discovery, archhub, livelabs, design, review_phase,
            code, import, implementation, pre_deployment, plan

    Returns:
        True if the specified gate has been approved, False otherwise.
    """
    gate_decisions = {
        "discovery": state.discovery_review_decision,
        "archhub": state.archhub_review_decision,
        "livelabs": state.livelabs_review_decision,
        "design": state.design_review_decision,
        "review_phase": (
            ReviewDecision.APPROVE
            if state.review_status == "approved"
            else None
        ),
        "code": state.code_review_decision,
        "import": state.import_review_decision,
        "implementation": state.implementation_review_decision,
        "pre_deployment": state.pre_deployment_review_decision,
        "plan": state.plan_review_decision,
    }

    decision = gate_decisions.get(gate_name)
    return decision == ReviewDecision.APPROVE
