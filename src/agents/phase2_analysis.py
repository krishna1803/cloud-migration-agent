"""
Phase 2: Analysis - Agent nodes for OCI target architecture design.

This phase analyzes the discovered architecture and designs the target OCI solution.
"""

from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models.state_schema import (
    MigrationState,
    PhaseStatus,
    OCIServiceMapping,
    ArchHubReference,
    LiveLabsWorkshop,
    SizingRecommendation,
    PricingEstimate
)
from src.utils.oci_genai import get_llm
from src.utils.logger import logger


# Phase 2 Node 1: Reconstruct Current State
def reconstruct_current_state(state: MigrationState) -> MigrationState:
    """
    Build comprehensive model of current source architecture.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with reconstructed architecture
    """
    try:
        logger.info(f"Reconstructing current state for migration {state.migration_id}")
        
        state.current_phase = "analysis"
        state.phase_status = PhaseStatus.IN_PROGRESS
        
        llm = get_llm()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a cloud architect reconstructing the current state 
            of a cloud environment for migration planning.
            
            Based on the discovered services and architecture, create a comprehensive
            model that includes:
            1. Service inventory with dependencies
            2. Network topology
            3. Data flows
            4. Security boundaries
            5. Performance characteristics
            
            Focus on accuracy and completeness."""),
            ("user", "Discovery data: {discovery}")
        ])
        
        # Reconstruct architecture
        chain = prompt | llm
        reconstruction = chain.invoke({
            "discovery": str(state.discovery.dict())
        })
        
        state.messages.append({
            "role": "system",
            "content": f"Current state reconstructed: {reconstruction}"
        })
        
        logger.info("Current state reconstruction complete")
        return state
        
    except Exception as e:
        logger.error(f"Current state reconstruction failed: {str(e)}")
        state.errors.append(f"Reconstruction error: {str(e)}")
        return state


# Phase 2 Node 2: Service Mapping
def service_mapping(state: MigrationState) -> MigrationState:
    """
    Map source services to OCI equivalents.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with service mappings
    """
    try:
        logger.info(f"Mapping services to OCI for migration {state.migration_id}")
        
        llm = get_llm()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an OCI migration expert. Map source cloud services
            to their OCI equivalents.
            
            For each source service, provide:
            - source_service: original service name
            - oci_service: recommended OCI service
            - mapping_confidence: 0-1 confidence score
            - alternatives: list of alternative OCI services
            - reasoning: explanation for the mapping
            
            Consider:
            - Feature parity
            - Performance characteristics
            - Cost optimization
            - OCI-specific advantages
            
            Common mappings:
            - AWS EC2 → OCI Compute (VM/BM)
            - AWS S3 → OCI Object Storage
            - AWS RDS → OCI Database (Autonomous/Base/MySQL)
            - AWS Lambda → OCI Functions
            - AWS ELB → OCI Load Balancer
            - AWS VPC → OCI VCN
            - Azure VM → OCI Compute
            - GCE → OCI Compute
            
            Respond with JSON array of mappings."""),
            ("user", "Source services: {services}\nProvider: {provider}")
        ])
        
        chain = prompt | llm | JsonOutputParser()
        mappings = chain.invoke({
            "services": str(state.discovery.discovered_services),
            "provider": state.source_provider
        })
        
        # Create mapping objects
        for mapping_data in mappings:
            mapping = OCIServiceMapping(**mapping_data)
            state.analysis.service_mappings.append(mapping)
        
        logger.info(f"Mapped {len(mappings)} services to OCI")
        return state
        
    except Exception as e:
        logger.error(f"Service mapping failed: {str(e)}")
        state.errors.append(f"Service mapping error: {str(e)}")
        return state


# Phase 2 Node 3: ArchHub Discovery (Parallel)
def archhub_discovery(state: MigrationState) -> MigrationState:
    """
    Discover relevant OCI ArchHub reference architectures.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with ArchHub recommendations
    """
    try:
        logger.info(f"Discovering ArchHub references for migration {state.migration_id}")
        
        # TODO: Implement actual ArchHub MCP tool integration
        # For now, create mock references
        
        mock_references = [
            ArchHubReference(
                architecture_id="arch-001",
                title="3-Tier Web Application on OCI",
                description="Scalable web application with load balancer, compute, and database",
                diagram_url="https://docs.oracle.com/en/solutions/...",
                components=["Load Balancer", "Compute", "Autonomous Database", "Object Storage"],
                match_score=0.85
            ),
            ArchHubReference(
                architecture_id="arch-002",
                title="Microservices on OCI Container Engine (OKE)",
                description="Container-based microservices architecture",
                diagram_url="https://docs.oracle.com/en/solutions/...",
                components=["OKE", "API Gateway", "Service Mesh", "Registry"],
                match_score=0.72
            )
        ]
        
        state.analysis.archhub_references = mock_references
        
        logger.info(f"Found {len(mock_references)} ArchHub references")
        return state
        
    except Exception as e:
        logger.error(f"ArchHub discovery failed: {str(e)}")
        state.errors.append(f"ArchHub error: {str(e)}")
        return state


# Phase 2 Node 4: LiveLabs Discovery (Parallel)
def livelabs_discovery(state: MigrationState) -> MigrationState:
    """
    Discover relevant LiveLabs workshops.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with LiveLabs recommendations
    """
    try:
        logger.info(f"Discovering LiveLabs workshops for migration {state.migration_id}")
        
        # TODO: Implement actual LiveLabs MCP tool integration
        # For now, create mock workshops
        
        mock_workshops = [
            LiveLabsWorkshop(
                workshop_id="ll-001",
                title="Migrate to OCI Compute",
                description="Learn to migrate virtual machines to OCI",
                url="https://apexapps.oracle.com/pls/apex/...",
                relevance_score=0.90,
                topics=["Compute", "Migration", "Networking"]
            ),
            LiveLabsWorkshop(
                workshop_id="ll-002",
                title="OCI Database Migration",
                description="Migrate databases to OCI Autonomous Database",
                url="https://apexapps.oracle.com/pls/apex/...",
                relevance_score=0.85,
                topics=["Database", "Migration", "Autonomous"]
            )
        ]
        
        state.analysis.livelabs_workshops = mock_workshops
        
        logger.info(f"Found {len(mock_workshops)} LiveLabs workshops")
        return state
        
    except Exception as e:
        logger.error(f"LiveLabs discovery failed: {str(e)}")
        state.errors.append(f"LiveLabs error: {str(e)}")
        return state


# Phase 2 Node 5: Target Design
def target_design(state: MigrationState) -> MigrationState:
    """
    Design target OCI architecture.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with target design
    """
    try:
        logger.info(f"Designing target OCI architecture for migration {state.migration_id}")
        
        llm = get_llm()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an OCI solutions architect designing a target architecture.
            
            Based on:
            - Service mappings
            - ArchHub reference architectures
            - LiveLabs best practices
            
            Create a comprehensive OCI target design that includes:
            1. Network architecture (VCN, subnets, gateways)
            2. Compute resources (shapes, configurations)
            3. Storage layout (Object Storage, Block Volumes, File Storage)
            4. Database configuration
            5. Security design (IAM, security lists, NSGs)
            6. High availability and disaster recovery
            
            Follow OCI best practices and Well-Architected Framework principles."""),
            ("user", """Service mappings: {mappings}
            ArchHub refs: {archhub}
            LiveLabs: {livelabs}""")
        ])
        
        chain = prompt | llm
        target_design = chain.invoke({
            "mappings": str([m.dict() for m in state.analysis.service_mappings]),
            "archhub": str([a.dict() for a in state.analysis.archhub_references]),
            "livelabs": str([l.dict() for l in state.analysis.livelabs_workshops])
        })
        
        state.messages.append({
            "role": "system",
            "content": f"Target OCI design: {target_design}"
        })
        
        logger.info("Target OCI architecture design complete")
        return state
        
    except Exception as e:
        logger.error(f"Target design failed: {str(e)}")
        state.errors.append(f"Target design error: {str(e)}")
        return state


# Phase 2 Node 6: Resource Sizing
def resource_sizing(state: MigrationState) -> MigrationState:
    """
    Size OCI resources based on source workload.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with sizing recommendations
    """
    try:
        logger.info(f"Sizing OCI resources for migration {state.migration_id}")
        
        # TODO: Implement actual sizing logic with MCP tool
        # For now, create mock sizing recommendations
        
        mock_sizing = [
            SizingRecommendation(
                resource_type="Compute",
                recommended_shape="VM.Standard.E4.Flex",
                vcpus=4,
                memory_gb=64,
                storage_gb=500,
                rationale="Sized for medium workload with flexibility"
            ),
            SizingRecommendation(
                resource_type="Database",
                recommended_shape="Autonomous Database",
                vcpus=2,
                memory_gb=16,
                storage_gb=1024,
                rationale="Autonomous for reduced management overhead"
            )
        ]
        
        state.analysis.sizing_recommendations = mock_sizing
        
        logger.info(f"Created {len(mock_sizing)} sizing recommendations")
        return state
        
    except Exception as e:
        logger.error(f"Resource sizing failed: {str(e)}")
        state.errors.append(f"Resource sizing error: {str(e)}")
        return state


# Phase 2 Node 7: Cost Estimation
def cost_estimation(state: MigrationState) -> MigrationState:
    """
    Estimate OCI costs for target architecture.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with cost estimates
    """
    try:
        logger.info(f"Estimating OCI costs for migration {state.migration_id}")
        
        # TODO: Implement actual cost estimation with pricing MCP tool
        # For now, create mock pricing
        
        mock_pricing = [
            PricingEstimate(
                resource_name="Compute - VM.Standard.E4.Flex (4 OCPUs, 64GB)",
                monthly_cost_usd=290.00,
                annual_cost_usd=3480.00,
                cost_breakdown={
                    "compute": 220.00,
                    "storage": 50.00,
                    "network": 20.00
                }
            ),
            PricingEstimate(
                resource_name="Autonomous Database (2 OCPUs)",
                monthly_cost_usd=580.00,
                annual_cost_usd=6960.00,
                cost_breakdown={
                    "database": 500.00,
                    "storage": 80.00
                }
            )
        ]
        
        state.analysis.pricing_estimates = mock_pricing
        
        # Calculate totals
        total_monthly = sum(p.monthly_cost_usd for p in mock_pricing)
        total_annual = sum(p.annual_cost_usd for p in mock_pricing)
        
        state.analysis.total_monthly_cost_usd = total_monthly
        state.analysis.total_annual_cost_usd = total_annual
        
        logger.info(
            f"Cost estimation complete: ${total_monthly:.2f}/month, "
            f"${total_annual:.2f}/year"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Cost estimation failed: {str(e)}")
        state.errors.append(f"Cost estimation error: {str(e)}")
        return state
