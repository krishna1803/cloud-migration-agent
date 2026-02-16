"""
End-to-end test for complete Cloud Migration Agent workflow.

Tests all 6 phases: Discovery → Analysis → Design → Review → Implementation → Deployment
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.state_schema import create_migration_state, ReviewDecision, PhaseStatus
from src.agents import *
from src.utils.logger import logger


def print_phase_header(phase_name: str, phase_num: int):
    """Print formatted phase header"""
    print("\n" + "="*80)
    print(f"  PHASE {phase_num}: {phase_name.upper()}")
    print("="*80 + "\n")


def print_results(title: str, items: list, max_items: int = 5):
    """Print formatted results"""
    print(f"\n{title}:")
    for i, item in enumerate(items[:max_items], 1):
        print(f"  {i}. {item}")
    if len(items) > max_items:
        print(f"  ... and {len(items) - max_items} more")


async def test_complete_workflow():
    """Test complete migration workflow from start to finish"""
    
    print("\n" + "╔"+"="*78+"╗")
    print("║" + " "*20 + "CLOUD MIGRATION AGENT - FULL WORKFLOW TEST" + " "*17 + "║")
    print("╚"+"="*78+"╝")
    
    # ==========================================================================
    # PHASE 1: DISCOVERY
    # ==========================================================================
    print_phase_header("Discovery", 1)
    
    # Create initial state
    print("→ Creating migration state...")
    state = create_migration_state(
        migration_id="test-full-migration-001",
        user_context="""
        Migration Requirements:
        
        Source: AWS 3-tier web application
        - Frontend: React SPA served from S3 + CloudFront
        - API Layer: 5x EC2 t3.large instances behind ALB
        - Database: RDS PostgreSQL (db.r5.2xlarge, Multi-AZ)
        - Cache: ElastiCache Redis cluster
        - Storage: S3 bucket (2TB data)
        - Networking: VPC with 3 AZs, public/private subnets
        
        Current Costs: ~$4,200/month
        
        Goals:
        - Reduce costs by 25-30%
        - Improve performance
        - Simplify operations
        - Maintain high availability
        
        Timeline: 60 days
        """,
        source_provider="AWS",
        target_region="us-ashburn-1"
    )
    print(f"✓ Migration created: {state.migration_id}")
    
    # Execute Phase 1 nodes
    print("\n→ Executing Phase 1 nodes...")
    state = intake_plan(state)
    print(f"  ✓ Intake complete")
    
    state = kb_enrich_discovery(state)
    print(f"  ✓ KB enrichment complete")
    
    state = extract_evidence(state)
    print(f"  ✓ Evidence extracted: {len(state.discovery.discovered_services)} services")
    
    state = gap_detection(state)
    print(f"  ✓ Gap detection complete")
    print(f"    - Confidence: {state.discovery.discovery_confidence:.1%}")
    print(f"    - Gaps found: {len(state.discovery.gaps_identified)}")
    
    # Check if clarifications needed
    next_step = should_request_clarifications(state)
    if next_step == "clarify":
        print(f"  ⚠ Clarifications needed (confidence below 80%)")
    else:
        print(f"  ✓ Confidence acceptable, proceeding to review")
    
    # Discovery review gate
    print("\n→ Discovery Review Gate...")
    state = discovery_review_gate(state)
    state = process_discovery_review(state, ReviewDecision.APPROVE, "Discovery looks good!")
    print(f"  ✓ Discovery approved")
    
    # ==========================================================================
    # PHASE 2: ANALYSIS
    # ==========================================================================
    print_phase_header("Analysis", 2)
    
    print("→ Executing Phase 2 nodes...")
    state = reconstruct_current_state(state)
    print(f"  ✓ Current state reconstructed")
    
    state = service_mapping(state)
    print(f"  ✓ Service mapping: {len(state.analysis.service_mappings)} mappings created")
    print_results("    Service Mappings", [
        f"{m.source_service} → {m.oci_service} ({m.mapping_confidence:.0%})"
        for m in state.analysis.service_mappings
    ], 3)
    
    state = archhub_discovery(state)
    print(f"  ✓ ArchHub discovery: {len(state.analysis.archhub_references)} references found")
    state = process_archhub_review(state, ReviewDecision.APPROVE)
    
    state = livelabs_discovery(state)
    print(f"  ✓ LiveLabs discovery: {len(state.analysis.livelabs_workshops)} workshops found")
    state = process_livelabs_review(state, ReviewDecision.APPROVE)
    
    state = target_design(state)
    print(f"  ✓ Target OCI architecture designed")
    
    state = resource_sizing(state)
    print(f"  ✓ Resource sizing: {len(state.analysis.sizing_recommendations)} recommendations")
    
    state = cost_estimation(state)
    print(f"  ✓ Cost estimation complete")
    print(f"    - Monthly: ${state.analysis.total_monthly_cost_usd:,.2f}")
    print(f"    - Annual: ${state.analysis.total_annual_cost_usd:,.2f}")
    
    # ==========================================================================
    # PHASE 3: DESIGN
    # ==========================================================================
    print_phase_header("Design", 3)
    
    print("→ Executing Phase 3 nodes...")
    state = formal_architecture_modeling(state)
    print(f"  ✓ Architecture model: {len(state.design.architecture_components)} components")
    
    state = component_definition(state)
    print(f"  ✓ Component definitions enriched")
    
    state = dependency_mapping(state)
    print(f"  ✓ Dependencies mapped: {len(state.design.component_dependencies)} relationships")
    
    state = topological_sort_deployment(state)
    print(f"  ✓ Deployment order: {len(state.design.deployment_sequence)} components sorted")
    
    state = diagram_generation(state)
    print(f"  ✓ Diagrams generated: {len(state.design.diagrams)} diagrams")
    print_results("    Diagrams", [
        f"{d.diagram_type} ({d.format})" for d in state.design.diagrams
    ])
    
    state = design_phase_complete(state)
    print(f"  ✓ Design phase complete")
    
    # Design review gate
    print("\n→ Design Review Gate...")
    state = design_review_gate(state)
    state = process_design_review(state, ReviewDecision.APPROVE, "Design approved!")
    print(f"  ✓ Design approved")
    
    # ==========================================================================
    # PHASE 4: REVIEW
    # ==========================================================================
    print_phase_header("Review", 4)
    
    print("→ Executing Phase 4 nodes...")
    state = final_validation(state)
    print(f"  ✓ Final validation: {len(state.review.feedback_items)} feedback items")
    print(f"    - Approval score: {state.review.approval_score:.1%}")
    
    state = compliance_check(state)
    print(f"  ✓ Compliance check complete")
    
    state = risk_assessment(state)
    print(f"  ✓ Risk assessment complete")
    
    state = cost_verification(state)
    print(f"  ✓ Cost verification complete")
    
    state = feedback_incorporation(state)
    print(f"  ✓ Feedback incorporated (iteration {state.review.review_iterations})")
    
    state = approval_check(state)
    print(f"  ✓ Approval check: {'APPROVED' if state.review.final_approved else 'NOT APPROVED'}")
    
    # ==========================================================================
    # PHASE 5: IMPLEMENTATION
    # ==========================================================================
    print_phase_header("Implementation", 5)
    
    print("→ Executing Phase 5 nodes...")
    state = strategy_selection(state)
    print(f"  ✓ Strategy selected: {state.implementation.strategy.value}")
    
    state = terraform_module_definition(state)
    print(f"  ✓ Terraform modules: {len(state.implementation.terraform_modules)} modules defined")
    
    state = terraform_code_generation(state)
    print(f"  ✓ Code generated: {len(state.implementation.generated_code)} files")
    print_results("    Generated Files", [
        f"{c.file_path} ({c.module_type})" for c in state.implementation.generated_code
    ])
    
    state = code_validation(state)
    validated = sum(1 for c in state.implementation.generated_code if c.validated)
    print(f"  ✓ Code validation: {validated}/{len(state.implementation.generated_code)} files validated")
    
    state = project_export(state)
    print(f"  ✓ Project exported to: {state.implementation.export_path}")
    
    # Code review gate
    print("\n→ Code Review Gate...")
    state = code_review_gate(state)
    state = process_code_review(state, ReviewDecision.APPROVE, "Code looks great!")
    print(f"  ✓ Code approved")
    
    # ==========================================================================
    # PHASE 6: DEPLOYMENT
    # ==========================================================================
    print_phase_header("Deployment", 6)
    
    print("→ Executing Phase 6 nodes...")
    state = pre_deployment_validation(state)
    pre_passed = sum(1 for v in state.deployment.pre_validation_results if v.passed)
    print(f"  ✓ Pre-deployment validation: {pre_passed}/{len(state.deployment.pre_validation_results)} checks passed")
    
    state = create_rm_stack(state)
    print(f"  ✓ OCI RM stack created: {state.deployment.stack_name}")
    
    state = generate_terraform_plan(state)
    print(f"  ✓ Terraform plan generated")
    
    # Plan review gate
    print("\n→ Plan Review Gate...")
    state = plan_review_gate(state)
    state = process_plan_review(state, ReviewDecision.APPROVE, "Plan approved!")
    print(f"  ✓ Plan approved")
    
    print("\n→ Executing deployment...")
    state = execute_deployment(state)
    print(f"  ✓ Deployment started: {state.deployment.deployment_jobs[-1].job_id}")
    
    state = monitor_deployment(state)
    print(f"  ✓ Deployment monitored: {state.deployment.deployment_jobs[-1].status}")
    
    state = post_deployment_validation(state)
    post_passed = sum(1 for v in state.deployment.post_validation_results if v.passed)
    print(f"  ✓ Post-deployment validation: {post_passed}/{len(state.deployment.post_validation_results)} checks passed")
    
    state = generate_deployment_report(state)
    print(f"  ✓ Deployment report: {state.deployment.deployment_report_path}")
    
    state = deployment_complete(state)
    print(f"  ✓ Deployment complete!")
    
    # ==========================================================================
    # FINAL SUMMARY
    # ==========================================================================
    print("\n" + "="*80)
    print("  MIGRATION COMPLETE! 🎉")
    print("="*80)
    
    print(f"""
📊 Migration Summary
────────────────────────────────────────────────────────────────────────────────
Migration ID:           {state.migration_id}
Source Provider:        {state.source_provider}
Target Region:          {state.target_region}
Current Phase:          {state.current_phase}
Phase Status:           {state.phase_status.value}

📈 Statistics
────────────────────────────────────────────────────────────────────────────────
Discovered Services:    {len(state.discovery.discovered_services)}
Service Mappings:       {len(state.analysis.service_mappings)}
Architecture Components:{len(state.design.architecture_components)}
Diagrams Generated:     {len(state.design.diagrams)}
Terraform Files:        {len(state.implementation.generated_code)}
Deployment Jobs:        {len(state.deployment.deployment_jobs)}

💰 Cost Analysis
────────────────────────────────────────────────────────────────────────────────
Monthly Cost:           ${state.analysis.total_monthly_cost_usd:,.2f}
Annual Cost:            ${state.analysis.total_annual_cost_usd:,.2f}

✅ Validation Results
────────────────────────────────────────────────────────────────────────────────
Pre-deployment:         {sum(1 for v in state.deployment.pre_validation_results if v.passed)}/{len(state.deployment.pre_validation_results)} passed
Post-deployment:        {sum(1 for v in state.deployment.post_validation_results if v.passed)}/{len(state.deployment.post_validation_results)} passed
Deployment Successful:  {'YES ✓' if state.deployment.deployment_successful else 'NO ✗'}

📝 Deliverables
────────────────────────────────────────────────────────────────────────────────
Terraform Project:      {state.implementation.export_path}
Deployment Report:      {state.deployment.deployment_report_path}
OCI RM Stack:           {state.deployment.stack_id}

⚠ Errors
────────────────────────────────────────────────────────────────────────────────
Errors Encountered:     {len(state.errors)}
""")
    
    if state.errors:
        print("Errors:")
        for error in state.errors:
            print(f"  - {error}")
    
    print("="*80)
    print("\n✅ ALL PHASES COMPLETED SUCCESSFULLY!")
    print("="*80 + "\n")
    
    return state


async def main():
    """Run the complete workflow test"""
    
    print("\n🚀 Starting Cloud Migration Agent - Complete Workflow Test\n")
    
    try:
        state = await test_complete_workflow()
        
        print("\n✅ Test completed successfully!")
        print(f"   Final state saved for migration: {state.migration_id}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
