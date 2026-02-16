"""
Test script for the Cloud Migration Agent Platform.

This script tests the core workflow functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.state_schema import create_migration_state, PhaseStatus
from src.agents.workflow import migration_workflow
from src.utils.logger import logger


async def test_discovery_phase():
    """Test Phase 1 (Discovery) execution"""
    
    print("\n" + "="*60)
    print("Testing Cloud Migration Agent - Phase 1 (Discovery)")
    print("="*60 + "\n")
    
    try:
        # Create initial migration state
        print("1. Creating migration state...")
        state = create_migration_state(
            migration_id="test-migration-001",
            user_context="""
            I need to migrate a 3-tier web application from AWS to OCI.
            The application consists of:
            - Load balancer (AWS ELB)
            - Web tier: 3x EC2 t3.large instances
            - App tier: 5x EC2 m5.xlarge instances
            - Database: RDS PostgreSQL (db.r5.2xlarge)
            - Storage: S3 bucket (500GB)
            - Network: VPC with 3 subnets
            
            Current monthly cost: ~$3,500/month
            Target: Reduce cost by 20-30% while maintaining performance
            """,
            source_provider="AWS",
            target_region="us-ashburn-1"
        )
        
        print(f"✓ Created migration: {state.migration_id}")
        print(f"  Source: {state.source_provider}")
        print(f"  Target: OCI {state.target_region}")
        
        # Note: Since we don't have actual checkpoint saver initialized
        # (would require Oracle DB), we'll simulate the workflow execution
        
        print("\n2. Simulating workflow execution...")
        
        # Manually execute nodes for testing
        from src.agents.phase1_discovery import (
            intake_plan,
            kb_enrich_discovery,
            extract_evidence,
            gap_detection
        )
        
        # Execute Phase 1 nodes
        print("\n   Running intake_plan...")
        state = intake_plan(state)
        print(f"   ✓ Phase: {state.current_phase}, Status: {state.phase_status}")
        
        print("\n   Running kb_enrich_discovery...")
        state = kb_enrich_discovery(state)
        print(f"   ✓ Messages: {len(state.messages)}")
        
        print("\n   Running extract_evidence...")
        state = extract_evidence(state)
        print(f"   ✓ Discovered services: {len(state.discovery.discovered_services)}")
        
        print("\n   Running gap_detection...")
        state = gap_detection(state)
        print(f"   ✓ Gaps identified: {len(state.discovery.gaps_identified)}")
        print(f"   ✓ Discovery confidence: {state.discovery.discovery_confidence:.1%}")
        
        # Check confidence threshold
        from src.agents.phase1_discovery import should_request_clarifications
        next_step = should_request_clarifications(state)
        
        print(f"\n3. Next step: {next_step}")
        
        if next_step == "clarify":
            print("\n   ⚠ Confidence below threshold - clarifications needed")
            print(f"   Questions: {len(state.discovery.clarifications_requested)}")
        else:
            print("\n   ✓ Confidence acceptable - proceeding to review gate")
        
        # Test Phase 2 nodes
        print("\n4. Testing Phase 2 (Analysis) nodes...")
        
        from src.agents.phase2_analysis import (
            service_mapping,
            archhub_discovery,
            livelabs_discovery
        )
        
        print("\n   Running service_mapping...")
        state = service_mapping(state)
        print(f"   ✓ Service mappings: {len(state.analysis.service_mappings)}")
        
        print("\n   Running archhub_discovery...")
        state = archhub_discovery(state)
        print(f"   ✓ ArchHub references: {len(state.analysis.archhub_references)}")
        
        print("\n   Running livelabs_discovery...")
        state = livelabs_discovery(state)
        print(f"   ✓ LiveLabs workshops: {len(state.analysis.livelabs_workshops)}")
        
        print("\n" + "="*60)
        print("✓ Test completed successfully!")
        print("="*60 + "\n")
        
        print("Summary:")
        print(f"  Migration ID: {state.migration_id}")
        print(f"  Current Phase: {state.current_phase}")
        print(f"  Phase Status: {state.phase_status}")
        print(f"  Discovered Services: {len(state.discovery.discovered_services)}")
        print(f"  Service Mappings: {len(state.analysis.service_mappings)}")
        print(f"  ArchHub References: {len(state.analysis.archhub_references)}")
        print(f"  Errors: {len(state.errors)}")
        
        if state.errors:
            print("\n⚠ Errors encountered:")
            for error in state.errors:
                print(f"  - {error}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_review_gates():
    """Test review gate functionality"""
    
    print("\n" + "="*60)
    print("Testing Review Gates")
    print("="*60 + "\n")
    
    try:
        from src.models.state_schema import ReviewDecision
        from src.agents.review_gates import (
            discovery_review_gate,
            process_discovery_review
        )
        
        # Create test state
        state = create_migration_state(
            migration_id="test-review-001",
            user_context="Test review gate",
            source_provider="AWS"
        )
        
        print("1. Testing discovery review gate...")
        state = discovery_review_gate(state)
        print(f"   ✓ Status: {state.phase_status}")
        print(f"   ✓ Phase: {state.current_phase}")
        
        print("\n2. Testing review approval...")
        state = process_discovery_review(
            state,
            ReviewDecision.APPROVE,
            "Looks good!"
        )
        print(f"   ✓ Decision: {state.discovery_review_decision}")
        print(f"   ✓ Feedback: {state.discovery_review_feedback}")
        print(f"   ✓ Status: {state.phase_status}")
        
        print("\n✓ Review gates test passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Review gates test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    
    print("\n" + "="*80)
    print(" "*20 + "CLOUD MIGRATION AGENT - TEST SUITE")
    print("="*80)
    
    results = []
    
    # Test 1: Discovery Phase
    result1 = await test_discovery_phase()
    results.append(("Discovery Phase", result1))
    
    # Test 2: Review Gates
    result2 = await test_review_gates()
    results.append(("Review Gates", result2))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:.<40} {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")
    print("="*80 + "\n")
    
    return all(passed for _, passed in results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
