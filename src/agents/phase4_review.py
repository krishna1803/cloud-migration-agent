"""
Phase 4: Review - Agent nodes for final validation and approval.

This phase performs final validation, incorporates feedback,
and obtains user approval before implementation.
"""

from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models.state_schema import (
    MigrationState,
    PhaseStatus,
    ReviewFeedback
)
from src.utils.oci_genai import get_llm
from src.utils.logger import logger


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
        logger.info(f"Performing final validation for migration {state.migration_id}")
        
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
        validation_results = chain.invoke({
            "components": str([c.dict() for c in state.design.architecture_components]),
            "mappings": str([m.dict() for m in state.analysis.service_mappings]),
            "cost": state.analysis.total_monthly_cost_usd,
            "diagram_count": len(state.design.diagrams)
        })
        
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
        
        logger.info(
            f"Validation complete: {passed_checks}/{total_checks} checks passed, "
            f"score: {state.review.approval_score:.1%}"
        )
        
        if critical_issues:
            logger.warning(f"Critical issues found: {len(critical_issues)}")
            state.messages.append({
                "role": "system",
                "content": f"⚠️ {len(critical_issues)} critical issues must be resolved before deployment"
            })
        
        return state
        
    except Exception as e:
        logger.error(f"Final validation failed: {str(e)}")
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
        logger.info(f"Performing compliance checks for migration {state.migration_id}")
        
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
        compliance_results = chain.invoke({
            "components": str([c.dict() for c in state.design.architecture_components]),
            "security": str(state.discovery.security_posture.dict() if state.discovery.security_posture else {}),
            "region": state.target_region
        })
        
        # Add compliance feedback
        for requirement, result in compliance_results.items():
            if not result.get("compliant", True):
                gaps = result.get("gaps", [])
                for gap in gaps:
                    feedback = ReviewFeedback(
                        feedback_type="concern",
                        description=f"[Compliance] {requirement}: {gap}",
                        priority="high"
                    )
                    state.review.feedback_items.append(feedback)
        
        logger.info("Compliance check complete")
        
        return state
        
    except Exception as e:
        logger.error(f"Compliance check failed: {str(e)}")
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
        logger.info(f"Assessing migration risks for migration {state.migration_id}")
        
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
        risks = chain.invoke({
            "source": state.source_provider,
            "components": str([c.dict() for c in state.design.architecture_components]),
            "component_count": len(state.design.architecture_components)
        })
        
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
        
        logger.info(f"Risk assessment complete: {len(risks)} risks identified")
        
        return state
        
    except Exception as e:
        logger.error(f"Risk assessment failed: {str(e)}")
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
        logger.info(f"Verifying cost estimates for migration {state.migration_id}")
        
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
        cost_verification = chain.invoke({
            "current_cost": source_cost,
            "oci_cost": state.analysis.total_monthly_cost_usd,
            "pricing": str([p.dict() for p in state.analysis.pricing_estimates])
        })
        
        # Add cost feedback if issues found
        if not cost_verification.get("verified", True):
            issues = cost_verification.get("issues", [])
            for issue in issues:
                feedback = ReviewFeedback(
                    feedback_type="concern",
                    description=f"[Cost] {issue}",
                    priority="medium"
                )
                state.review.feedback_items.append(feedback)
        
        # Add optimization recommendations
        optimizations = cost_verification.get("optimizations", [])
        for opt in optimizations:
            feedback = ReviewFeedback(
                feedback_type="change_request",
                description=f"[Cost Optimization] {opt}",
                priority="low"
            )
            state.review.feedback_items.append(feedback)
        
        logger.info("Cost verification complete")
        
        return state
        
    except Exception as e:
        logger.error(f"Cost verification failed: {str(e)}")
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
        logger.info(f"Incorporating feedback for migration {state.migration_id}")
        
        # Check if there's unresolved critical/high feedback
        critical_unresolved = [
            f for f in state.review.feedback_items 
            if f.priority in ["critical", "high"] and not f.resolved
        ]
        
        if critical_unresolved:
            logger.warning(f"{len(critical_unresolved)} critical/high priority items unresolved")
            state.messages.append({
                "role": "system",
                "content": f"⚠️ {len(critical_unresolved)} high priority items require attention"
            })
        
        # Increment review iteration
        state.review.review_iterations += 1
        
        logger.info(f"Feedback incorporation complete (iteration {state.review.review_iterations})")
        
        return state
        
    except Exception as e:
        logger.error(f"Feedback incorporation failed: {str(e)}")
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
        logger.info(f"Checking approval criteria for migration {state.migration_id}")
        
        from src.utils.config import config
        threshold = config.app.review_approval_threshold
        
        # Check approval score
        if state.review.approval_score >= threshold:
            state.review.final_approved = True
            state.phase_status = PhaseStatus.COMPLETED
            logger.info(f"Approval criteria met: {state.review.approval_score:.1%} >= {threshold:.1%}")
        else:
            state.review.final_approved = False
            logger.warning(f"Approval criteria not met: {state.review.approval_score:.1%} < {threshold:.1%}")
            state.messages.append({
                "role": "system",
                "content": f"Approval score {state.review.approval_score:.1%} below threshold {threshold:.1%}"
            })
        
        return state
        
    except Exception as e:
        logger.error(f"Approval check failed: {str(e)}")
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
        return "proceed"
    
    # Check iteration limit
    max_iterations = 5
    if state.review.review_iterations >= max_iterations:
        logger.warning(f"Maximum review iterations ({max_iterations}) reached")
        return "proceed"  # Force proceed after max iterations
    
    # Check if approval score is improving
    if state.review.approval_score < config.app.review_approval_threshold:
        return "iterate"
    
    return "proceed"
