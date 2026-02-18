"""
Phase 4: Review - Agent nodes for final validation and approval.

This phase performs final validation, incorporates feedback,
and obtains user approval before implementation.
"""

import time
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models.state_schema import (
    MigrationState,
    PhaseStatus,
    ReviewFeedback
)
from src.utils.oci_genai import get_llm
from src.utils.logger import logger, log_node_entry, log_node_exit, log_llm_call, log_error


# Phase 4 Node 1: Final Validation
def final_validation(state: MigrationState) -> MigrationState:
    """
    Perform comprehensive validation checks.

    Validates:
    - Architecture completeness
    - OCI best practices compliance
    - Security requirements
    - Cost alignment
    - Dependency integrity

    Args:
        state: Current migration state

    Returns:
        Updated state with validation results
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "review", "final_validation", {
            "components": len(state.design.architecture_components),
            "mappings": len(state.analysis.service_mappings),
            "total_monthly_cost_usd": state.analysis.total_monthly_cost_usd,
            "diagrams": len(state.design.diagrams),
        })

        state.current_phase = "review"
        state.phase_status = PhaseStatus.IN_PROGRESS

        llm = get_llm()

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are validating an OCI migration architecture for production readiness.

            Perform comprehensive validation across these dimensions:

            1. **Architecture Completeness**
               - All required components defined
               - No missing dependencies
               - Proper network design
               - Storage adequately provisioned

            2. **OCI Best Practices**
               - Multi-AD deployment where appropriate
               - Proper use of compartments
               - Security list/NSG configuration
               - IAM policies defined

            3. **Security & Compliance**
               - Encryption at rest and in transit
               - Proper authentication/authorization
               - Network isolation
               - Audit logging enabled

            4. **Cost Optimization**
               - Right-sized instances
               - Reserved capacity opportunities
               - Storage tier optimization
               - Unnecessary resources eliminated

            5. **High Availability & DR**
               - Redundancy where needed
               - Backup strategy defined
               - Disaster recovery plan
               - RTO/RPO requirements met

            For each validation area, provide:
            - passed: boolean
            - issues: list of specific issues found
            - recommendations: list of recommendations
            - severity: critical/high/medium/low

            Respond with JSON object with validation results for each area.
            """),
            ("user", """Architecture components: {components}
            Service mappings: {mappings}
            Cost estimate: ${cost}/month
            Design diagrams: {diagram_count} diagrams""")
        ])

        chain = prompt | llm | JsonOutputParser()
        t_llm = time.time()
        validation_results = chain.invoke({
            "components": str([c.dict() for c in state.design.architecture_components]),
            "mappings": str([m.dict() for m in state.analysis.service_mappings]),
            "cost": state.analysis.total_monthly_cost_usd,
            "diagram_count": len(state.design.diagrams),
        })
        llm_ms = (time.time() - t_llm) * 1000

        areas = list(validation_results.keys())
        passed_areas = [a for a in areas if validation_results[a].get("passed", False)]
        log_llm_call(
            state.migration_id,
            "final_validation",
            prompt_preview=(
                f"components={len(state.design.architecture_components)}, "
                f"cost=${state.analysis.total_monthly_cost_usd:.2f}"
            ),
            response_preview=(
                f"areas={areas}, passed={passed_areas}"
            ),
            duration_ms=llm_ms,
        )

        # Process validation results
        critical_issues = []
        high_issues = []
        medium_issues = []

        for area, results in validation_results.items():
            if not results.get("passed", True):
                issues = results.get("issues", [])
                severity = results.get("severity", "medium")

                for issue in issues:
                    feedback = ReviewFeedback(
                        feedback_type="concern",
                        description=f"[{area}] {issue}",
                        priority=severity
                    )
                    state.review.feedback_items.append(feedback)

                    if severity == "critical":
                        critical_issues.append(issue)
                    elif severity == "high":
                        high_issues.append(issue)
                    else:
                        medium_issues.append(issue)

        # Calculate approval score
        total_checks = len(validation_results)
        passed_checks = sum(1 for r in validation_results.values() if r.get("passed", False))
        state.review.approval_score = passed_checks / total_checks if total_checks > 0 else 0

        if critical_issues:
            state.messages.append({
                "role": "system",
                "content": f"⚠️ {len(critical_issues)} critical issues must be resolved before deployment"
            })

        log_node_exit(state.migration_id, "review", "final_validation", {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "approval_score": f"{state.review.approval_score:.1%}",
            "critical_issues": len(critical_issues),
            "high_issues": len(high_issues),
            "medium_issues": len(medium_issues),
            "feedback_items_added": len(critical_issues) + len(high_issues) + len(medium_issues),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "final_validation_error", str(e), phase="review")
        state.errors.append(f"Validation error: {str(e)}")
        return state


# Phase 4 Node 2: Compliance Check
def compliance_check(state: MigrationState) -> MigrationState:
    """
    Check compliance with regulatory and organizational requirements.

    Args:
        state: Current migration state

    Returns:
        Updated state with compliance results
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "review", "compliance_check", {
            "components": len(state.design.architecture_components),
            "target_region": state.target_region,
        })

        llm = get_llm()

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are checking OCI architecture for compliance requirements.

            Validate compliance with:
            1. Data residency requirements
            2. Industry regulations (HIPAA, PCI-DSS, SOC2, etc.)
            3. Encryption requirements
            4. Audit logging requirements
            5. Access control policies
            6. Data retention policies

            For each requirement, indicate:
            - compliant: boolean
            - gaps: list of compliance gaps
            - remediation: recommended actions

            Respond with JSON object."""),
            ("user", """Architecture: {components}
            Security posture: {security}
            Target region: {region}""")
        ])

        chain = prompt | llm | JsonOutputParser()
        t_llm = time.time()
        compliance_results = chain.invoke({
            "components": str([c.dict() for c in state.design.architecture_components]),
            "security": str(state.discovery.security_posture.dict() if state.discovery.security_posture else {}),
            "region": state.target_region,
        })
        llm_ms = (time.time() - t_llm) * 1000

        non_compliant = [k for k, v in compliance_results.items() if not v.get("compliant", True)]
        log_llm_call(
            state.migration_id,
            "compliance_check",
            prompt_preview=f"region={state.target_region}, components={len(state.design.architecture_components)}",
            response_preview=(
                f"requirements_checked={len(compliance_results)}, "
                f"non_compliant={non_compliant}"
            ),
            duration_ms=llm_ms,
        )

        # Add compliance feedback
        gaps_found = 0
        for requirement, result in compliance_results.items():
            if not result.get("compliant", True):
                gaps = result.get("gaps", [])
                gaps_found += len(gaps)
                for gap in gaps:
                    feedback = ReviewFeedback(
                        feedback_type="concern",
                        description=f"[Compliance] {requirement}: {gap}",
                        priority="high"
                    )
                    state.review.feedback_items.append(feedback)

        log_node_exit(state.migration_id, "review", "compliance_check", {
            "requirements_checked": len(compliance_results),
            "non_compliant_areas": len(non_compliant),
            "compliance_gaps_found": gaps_found,
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "compliance_check_error", str(e), phase="review")
        state.errors.append(f"Compliance check error: {str(e)}")
        return state


# Phase 4 Node 3: Risk Assessment
def risk_assessment(state: MigrationState) -> MigrationState:
    """
    Assess migration risks and provide mitigation strategies.

    Args:
        state: Current migration state

    Returns:
        Updated state with risk assessment
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "review", "risk_assessment", {
            "source_provider": state.source_provider,
            "component_count": len(state.design.architecture_components),
        })

        llm = get_llm()

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are assessing risks for a cloud migration to OCI.

            Identify risks across:
            1. **Technical Risks**
               - Integration challenges
               - Data migration complexity
               - Performance issues
               - Compatibility problems

            2. **Operational Risks**
               - Downtime during migration
               - Resource availability
               - Skills gap
               - Support challenges

            3. **Business Risks**
               - Cost overruns
               - Timeline delays
               - Business continuity
               - Vendor lock-in

            4. **Security Risks**
               - Data exposure during migration
               - Access control gaps
               - Compliance violations

            For each risk:
            - risk_name: descriptive name
            - likelihood: low/medium/high
            - impact: low/medium/high
            - mitigation: mitigation strategy
            - risk_score: 1-10

            Respond with JSON array of risk objects."""),
            ("user", """Source provider: {source}
            Target architecture: {components}
            Complexity: {component_count} components""")
        ])

        chain = prompt | llm | JsonOutputParser()
        t_llm = time.time()
        risks = chain.invoke({
            "source": state.source_provider,
            "components": str([c.dict() for c in state.design.architecture_components]),
            "component_count": len(state.design.architecture_components),
        })
        llm_ms = (time.time() - t_llm) * 1000

        high_risks = [r for r in risks if r.get("risk_score", 0) >= 7]
        risk_by_likelihood = {"low": 0, "medium": 0, "high": 0}
        for r in risks:
            risk_by_likelihood[r.get("likelihood", "medium")] = (
                risk_by_likelihood.get(r.get("likelihood", "medium"), 0) + 1
            )
        log_llm_call(
            state.migration_id,
            "risk_assessment",
            prompt_preview=(
                f"source={state.source_provider}, "
                f"components={len(state.design.architecture_components)}"
            ),
            response_preview=(
                f"risks_identified={len(risks)}, high_risk={len(high_risks)}, "
                f"by_likelihood={risk_by_likelihood}"
            ),
            duration_ms=llm_ms,
        )

        # Add high-risk items as feedback
        for risk in risks:
            risk_score = risk.get("risk_score", 0)
            if risk_score >= 7:  # High risk
                feedback = ReviewFeedback(
                    feedback_type="concern",
                    description=f"[Risk] {risk['risk_name']}: {risk.get('mitigation', 'No mitigation defined')}",
                    priority="high"
                )
                state.review.feedback_items.append(feedback)

        # Store risk assessment in messages
        state.messages.append({
            "role": "system",
            "content": f"Risk assessment: {len(risks)} risks identified"
        })

        log_node_exit(state.migration_id, "review", "risk_assessment", {
            "risks_identified": len(risks),
            "high_risk_count": len(high_risks),
            "high_risk_names": str([r.get("risk_name", "?") for r in high_risks]),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "risk_assessment_error", str(e), phase="review")
        state.errors.append(f"Risk assessment error: {str(e)}")
        return state


# Phase 4 Node 4: Cost Verification
def cost_verification(state: MigrationState) -> MigrationState:
    """
    Verify cost estimates and identify optimization opportunities.

    Args:
        state: Current migration state

    Returns:
        Updated state with cost verification
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "review", "cost_verification", {
            "oci_monthly_cost_usd": state.analysis.total_monthly_cost_usd,
            "pricing_estimates_count": len(state.analysis.pricing_estimates),
            "has_bom": bool(state.bom_file),
        })

        llm = get_llm()

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are verifying OCI cost estimates for accuracy.

            Review the cost breakdown and:
            1. Verify calculations are reasonable
            2. Identify cost optimization opportunities
            3. Compare with source cloud costs
            4. Flag any unexpected costs

            Provide:
            - verified: boolean (costs seem accurate)
            - issues: list of cost issues found
            - optimizations: list of cost optimization recommendations
            - potential_savings: estimated monthly savings in USD

            Respond with JSON object."""),
            ("user", """Current monthly cost: ${current_cost}
            Estimated OCI cost: ${oci_cost}/month
            Pricing estimates: {pricing}""")
        ])

        # Get source cost from BOM or estimates
        source_cost = 0
        if state.bom_file:
            # Would extract from BOM
            source_cost = 3500  # Placeholder

        chain = prompt | llm | JsonOutputParser()
        t_llm = time.time()
        cost_result = chain.invoke({
            "current_cost": source_cost,
            "oci_cost": state.analysis.total_monthly_cost_usd,
            "pricing": str([p.dict() for p in state.analysis.pricing_estimates]),
        })
        llm_ms = (time.time() - t_llm) * 1000

        optimizations = cost_result.get("optimizations", [])
        log_llm_call(
            state.migration_id,
            "cost_verification",
            prompt_preview=(
                f"source_cost=${source_cost}, "
                f"oci_cost=${state.analysis.total_monthly_cost_usd:.2f}, "
                f"pricing_items={len(state.analysis.pricing_estimates)}"
            ),
            response_preview=(
                f"verified={cost_result.get('verified', '?')}, "
                f"issues={len(cost_result.get('issues', []))}, "
                f"optimizations={len(optimizations)}, "
                f"potential_savings=${cost_result.get('potential_savings', 0)}"
            ),
            duration_ms=llm_ms,
        )

        # Add cost feedback if issues found
        if not cost_result.get("verified", True):
            issues = cost_result.get("issues", [])
            for issue in issues:
                feedback = ReviewFeedback(
                    feedback_type="concern",
                    description=f"[Cost] {issue}",
                    priority="medium"
                )
                state.review.feedback_items.append(feedback)

        # Add optimization recommendations
        for opt in optimizations:
            feedback = ReviewFeedback(
                feedback_type="change_request",
                description=f"[Cost Optimization] {opt}",
                priority="low"
            )
            state.review.feedback_items.append(feedback)

        log_node_exit(state.migration_id, "review", "cost_verification", {
            "verified": cost_result.get("verified", True),
            "issues_found": len(cost_result.get("issues", [])),
            "optimizations_found": len(optimizations),
            "potential_savings_usd": cost_result.get("potential_savings", 0),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "cost_verification_error", str(e), phase="review")
        state.errors.append(f"Cost verification error: {str(e)}")
        return state


# Phase 4 Node 5: Feedback Incorporation
def feedback_incorporation(state: MigrationState) -> MigrationState:
    """
    Incorporate user feedback and iterate if needed.

    Args:
        state: Current migration state

    Returns:
        Updated state with feedback incorporated
    """
    try:
        t0 = time.time()
        total_feedback = len(state.review.feedback_items)
        unresolved = [f for f in state.review.feedback_items if not f.resolved]
        log_node_entry(state.migration_id, "review", "feedback_incorporation", {
            "total_feedback_items": total_feedback,
            "unresolved_items": len(unresolved),
            "review_iteration": state.review.review_iterations,
        })

        # Check if there's unresolved critical/high feedback
        critical_unresolved = [
            f for f in state.review.feedback_items
            if f.priority in ["critical", "high"] and not f.resolved
        ]

        if critical_unresolved:
            logger.warning(
                f"[REVIEW:feedback_incorporation] {len(critical_unresolved)} "
                f"critical/high priority items unresolved for migration {state.migration_id}"
            )
            state.messages.append({
                "role": "system",
                "content": f"⚠️ {len(critical_unresolved)} high priority items require attention"
            })

        # Increment review iteration
        state.review.review_iterations += 1

        log_node_exit(state.migration_id, "review", "feedback_incorporation", {
            "critical_high_unresolved": len(critical_unresolved),
            "review_iteration_now": state.review.review_iterations,
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "feedback_incorporation_error", str(e), phase="review")
        state.errors.append(f"Feedback incorporation error: {str(e)}")
        return state


# Phase 4 Node 6: Approval Check
def approval_check(state: MigrationState) -> MigrationState:
    """
    Check if design meets approval criteria.

    Args:
        state: Current migration state

    Returns:
        Updated state with approval status
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "review", "approval_check", {
            "approval_score": f"{state.review.approval_score:.1%}",
            "review_iterations": state.review.review_iterations,
            "feedback_items": len(state.review.feedback_items),
        })

        from src.utils.config import config
        threshold = config.app.review_approval_threshold

        # Check approval score
        if state.review.approval_score >= threshold:
            state.review.final_approved = True
            state.phase_status = PhaseStatus.COMPLETED
            logger.info(
                f"[REVIEW:approval_check] APPROVED for migration {state.migration_id}: "
                f"{state.review.approval_score:.1%} >= {threshold:.1%}"
            )
        else:
            state.review.final_approved = False
            logger.warning(
                f"[REVIEW:approval_check] NOT APPROVED for migration {state.migration_id}: "
                f"{state.review.approval_score:.1%} < {threshold:.1%}"
            )
            state.messages.append({
                "role": "system",
                "content": f"Approval score {state.review.approval_score:.1%} below threshold {threshold:.1%}"
            })

        log_node_exit(state.migration_id, "review", "approval_check", {
            "final_approved": state.review.final_approved,
            "approval_score": f"{state.review.approval_score:.1%}",
            "threshold": f"{threshold:.1%}",
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "approval_check_error", str(e), phase="review")
        state.errors.append(f"Approval check error: {str(e)}")
        return state


# Conditional: Should iterate review?
def should_iterate_review(state: MigrationState) -> str:
    """
    Determine if review should iterate or proceed.

    Args:
        state: Current migration state

    Returns:
        "iterate" if more review needed, "proceed" otherwise
    """
    from src.utils.config import config

    # Check if approved
    if state.review.final_approved:
        logger.info(
            f"[REVIEW:should_iterate_review] PROCEED — approved "
            f"(score={state.review.approval_score:.1%}, iteration={state.review.review_iterations})"
        )
        return "proceed"

    # Check iteration limit
    max_iterations = 5
    if state.review.review_iterations >= max_iterations:
        logger.warning(
            f"[REVIEW:should_iterate_review] PROCEED (forced) — max iterations "
            f"({max_iterations}) reached for migration {state.migration_id}"
        )
        return "proceed"  # Force proceed after max iterations

    # Check if approval score is improving
    if state.review.approval_score < config.app.review_approval_threshold:
        logger.info(
            f"[REVIEW:should_iterate_review] ITERATE — score {state.review.approval_score:.1%} "
            f"below threshold {config.app.review_approval_threshold:.1%}, "
            f"iteration {state.review.review_iterations}/{max_iterations}"
        )
        return "iterate"

    logger.info(
        f"[REVIEW:should_iterate_review] PROCEED — score {state.review.approval_score:.1%} "
        f"meets threshold"
    )
    return "proceed"
