"""
Phase 3: Design - Agent nodes for formal architecture modeling.

This phase creates formal architecture models with components,
dependencies, and deployment sequences.
"""

import json
import networkx as nx
from typing import Dict, Any, List, Set
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models.state_schema import (
    MigrationState,
    PhaseStatus,
    ArchitectureComponent,
    DesignDiagram
)
from src.utils.oci_genai import get_llm
from src.utils.logger import logger


# Phase 3 Node 1: Formal Architecture Modeling
def formal_architecture_modeling(state: MigrationState) -> MigrationState:
    """
    Create formal architecture state machine.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with formal architecture model
    """
    try:
        logger.info(f"Creating formal architecture model for migration {state.migration_id}")
        
        state.current_phase = "design"
        state.phase_status = PhaseStatus.IN_PROGRESS
        
        llm = get_llm()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are creating a formal architecture model for OCI migration.
            
            Based on the analysis phase (service mappings, sizing, target design),
            create a structured architecture model with:
            
            1. Components - Each OCI service/resource with:
               - component_id: unique identifier (e.g., "comp_lb_001")
               - component_type: resource type (compute, network, storage, database)
               - name: descriptive name
               - oci_service: OCI service name (e.g., "Load Balancer", "Compute Instance")
               - configuration: detailed configuration as JSON
               - dependencies: list of component_ids this depends on
               - deployment_order: will be calculated later
            
            2. Follow OCI best practices:
               - VCN and subnets first
               - Internet/NAT gateways next
               - Security lists and NSGs
               - Load balancers
               - Compute instances
               - Databases
               - Object storage
            
            Respond with a JSON array of component objects.
            """),
            ("user", """Service mappings: {mappings}
            Sizing recommendations: {sizing}
            Target design: {target_design}""")
        ])
        
        chain = prompt | llm | JsonOutputParser()
        components_data = chain.invoke({
            "mappings": str([m.dict() for m in state.analysis.service_mappings]),
            "sizing": str([s.dict() for s in state.analysis.sizing_recommendations]),
            "target_design": str(state.messages[-1]["content"] if state.messages else "")
        })
        
        # Create component objects
        for comp_data in components_data:
            component = ArchitectureComponent(**comp_data)
            state.design.architecture_components.append(component)
        
        logger.info(f"Created {len(components_data)} architecture components")
        
        return state
        
    except Exception as e:
        logger.error(f"Formal architecture modeling failed: {str(e)}")
        state.errors.append(f"Architecture modeling error: {str(e)}")
        return state


# Phase 3 Node 2: Component Definition
def component_definition(state: MigrationState) -> MigrationState:
    """
    Define detailed configuration for each component.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with enriched component definitions
    """
    try:
        logger.info(f"Defining component details for migration {state.migration_id}")
        
        llm = get_llm()
        
        # Enrich each component with detailed configuration
        for component in state.design.architecture_components:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are detailing OCI resource configuration.
                
                For the given component, provide complete configuration including:
                - Network settings (CIDR blocks, subnets)
                - Instance specifications (shape, OS, storage)
                - Security settings (security lists, NSGs, IAM)
                - High availability settings
                - Backup/DR configuration
                
                Use OCI-specific terminology and values.
                Respond with JSON configuration object."""),
                ("user", """Component: {component}
                Component type: {comp_type}
                OCI service: {oci_service}""")
            ])
            
            chain = prompt | llm | JsonOutputParser()
            detailed_config = chain.invoke({
                "component": component.name,
                "comp_type": component.component_type,
                "oci_service": component.oci_service
            })
            
            # Update component configuration
            component.configuration.update(detailed_config)
        
        logger.info("Component definitions enriched")
        
        return state
        
    except Exception as e:
        logger.error(f"Component definition failed: {str(e)}")
        state.errors.append(f"Component definition error: {str(e)}")
        return state


# Phase 3 Node 3: Dependency Mapping
def dependency_mapping(state: MigrationState) -> MigrationState:
    """
    Map dependencies between components.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with dependency graph
    """
    try:
        logger.info(f"Mapping component dependencies for migration {state.migration_id}")
        
        llm = get_llm()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are mapping dependencies between OCI components.
            
            Analyze the components and determine which components depend on others.
            
            Rules:
            - Network resources (VCN, subnets, gateways) have no dependencies
            - Security resources depend on network resources
            - Compute depends on network and security
            - Load balancers depend on network and compute
            - Databases depend on network and security
            
            For each component, list the component_ids it depends on.
            
            Respond with JSON object: {component_id: [dependency_ids]}
            """),
            ("user", "Components: {components}")
        ])
        
        chain = prompt | llm | JsonOutputParser()
        dependencies = chain.invoke({
            "components": str([c.dict() for c in state.design.architecture_components])
        })
        
        # Update component dependencies and state
        state.design.component_dependencies = dependencies
        
        for component in state.design.architecture_components:
            if component.component_id in dependencies:
                component.dependencies = dependencies[component.component_id]
        
        logger.info(f"Mapped dependencies for {len(dependencies)} components")
        
        return state
        
    except Exception as e:
        logger.error(f"Dependency mapping failed: {str(e)}")
        state.errors.append(f"Dependency mapping error: {str(e)}")
        return state


# Phase 3 Node 4: Topological Sort for Deployment Order
def topological_sort_deployment(state: MigrationState) -> MigrationState:
    """
    Calculate deployment order using topological sort.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with deployment sequence
    """
    try:
        logger.info(f"Computing deployment order for migration {state.migration_id}")
        
        # Build directed graph
        G = nx.DiGraph()
        
        # Add all components as nodes
        for component in state.design.architecture_components:
            G.add_node(component.component_id, component=component)
        
        # Add edges (dependency -> dependent)
        for component in state.design.architecture_components:
            for dependency in component.dependencies:
                G.add_edge(dependency, component.component_id)
        
        # Check for cycles
        if not nx.is_directed_acyclic_graph(G):
            cycles = list(nx.simple_cycles(G))
            error_msg = f"Circular dependencies detected: {cycles}"
            logger.error(error_msg)
            state.errors.append(error_msg)
            return state
        
        # Topological sort
        deployment_order = list(nx.topological_sort(G))
        state.design.deployment_sequence = deployment_order
        
        # Assign deployment order to components
        for idx, component_id in enumerate(deployment_order, 1):
            for component in state.design.architecture_components:
                if component.component_id == component_id:
                    component.deployment_order = idx
                    break
        
        logger.info(f"Deployment order computed: {len(deployment_order)} components")
        
        return state
        
    except Exception as e:
        logger.error(f"Topological sort failed: {str(e)}")
        state.errors.append(f"Topological sort error: {str(e)}")
        return state


# Phase 3 Node 5: Diagram Generation
def diagram_generation(state: MigrationState) -> MigrationState:
    """
    Generate architecture diagrams (logical, sequence, Gantt).
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with generated diagrams
    """
    try:
        logger.info(f"Generating architecture diagrams for migration {state.migration_id}")
        
        # Generate Mermaid diagrams (can be rendered in UI)
        
        # 1. Logical Architecture Diagram
        logical_diagram = generate_logical_diagram(state)
        state.design.diagrams.append(DesignDiagram(
            diagram_type="logical",
            diagram_data=logical_diagram,
            format="mermaid"
        ))
        
        # 2. Sequence Diagram (Deployment Flow)
        sequence_diagram = generate_sequence_diagram(state)
        state.design.diagrams.append(DesignDiagram(
            diagram_type="sequence",
            diagram_data=sequence_diagram,
            format="mermaid"
        ))
        
        # 3. Gantt Chart (Deployment Timeline)
        gantt_diagram = generate_gantt_diagram(state)
        state.design.diagrams.append(DesignDiagram(
            diagram_type="gantt",
            diagram_data=gantt_diagram,
            format="mermaid"
        ))
        
        # 4. Network Diagram
        network_diagram = generate_network_diagram(state)
        state.design.diagrams.append(DesignDiagram(
            diagram_type="network",
            diagram_data=network_diagram,
            format="mermaid"
        ))
        
        logger.info(f"Generated {len(state.design.diagrams)} diagrams")
        
        return state
        
    except Exception as e:
        logger.error(f"Diagram generation failed: {str(e)}")
        state.errors.append(f"Diagram generation error: {str(e)}")
        return state


def generate_logical_diagram(state: MigrationState) -> str:
    """Generate Mermaid logical architecture diagram"""
    
    diagram = ["graph TD"]
    
    # Group components by type
    by_type = {}
    for comp in state.design.architecture_components:
        comp_type = comp.component_type
        if comp_type not in by_type:
            by_type[comp_type] = []
        by_type[comp_type].append(comp)
    
    # Add nodes
    for comp in state.design.architecture_components:
        label = f"{comp.name}<br/>{comp.oci_service}"
        diagram.append(f"    {comp.component_id}[{label}]")
    
    # Add edges
    for comp in state.design.architecture_components:
        for dep in comp.dependencies:
            diagram.append(f"    {dep} --> {comp.component_id}")
    
    # Add styling
    diagram.append("    classDef network fill:#e3f2fd")
    diagram.append("    classDef compute fill:#fff3e0")
    diagram.append("    classDef database fill:#f3e5f5")
    diagram.append("    classDef storage fill:#e8f5e9")
    
    for comp_type, comps in by_type.items():
        for comp in comps:
            if comp_type == "network":
                diagram.append(f"    class {comp.component_id} network")
            elif comp_type == "compute":
                diagram.append(f"    class {comp.component_id} compute")
            elif comp_type == "database":
                diagram.append(f"    class {comp.component_id} database")
            elif comp_type == "storage":
                diagram.append(f"    class {comp.component_id} storage")
    
    return "\n".join(diagram)


def generate_sequence_diagram(state: MigrationState) -> str:
    """Generate Mermaid sequence diagram for deployment"""
    
    diagram = ["sequenceDiagram"]
    diagram.append("    participant User")
    diagram.append("    participant OCI_RM as OCI Resource Manager")
    diagram.append("    participant Terraform")
    
    for comp_id in state.design.deployment_sequence[:10]:  # First 10 for clarity
        comp = next((c for c in state.design.architecture_components 
                    if c.component_id == comp_id), None)
        if comp:
            diagram.append(f"    User->>OCI_RM: Deploy {comp.name}")
            diagram.append(f"    OCI_RM->>Terraform: Execute plan")
            diagram.append(f"    Terraform->>OCI_RM: Create {comp.oci_service}")
            diagram.append(f"    OCI_RM->>User: {comp.name} deployed")
    
    return "\n".join(diagram)


def generate_gantt_diagram(state: MigrationState) -> str:
    """Generate Mermaid Gantt chart for deployment timeline"""
    
    diagram = ["gantt"]
    diagram.append("    title OCI Migration Deployment Timeline")
    diagram.append("    dateFormat YYYY-MM-DD")
    diagram.append("    section Network")
    
    # Add tasks by phase (simplified)
    current_section = "Network"
    for idx, comp_id in enumerate(state.design.deployment_sequence):
        comp = next((c for c in state.design.architecture_components 
                    if c.component_id == comp_id), None)
        if comp:
            if comp.component_type != current_section.lower():
                current_section = comp.component_type.capitalize()
                diagram.append(f"    section {current_section}")
            
            # Simple timeline (each task 1 day, sequential)
            diagram.append(f"    {comp.name} : {idx}, 1d")
    
    return "\n".join(diagram)


def generate_network_diagram(state: MigrationState) -> str:
    """Generate Mermaid network topology diagram"""
    
    diagram = ["graph TB"]
    
    # Add network components
    network_comps = [c for c in state.design.architecture_components 
                     if c.component_type == "network"]
    
    for comp in network_comps:
        diagram.append(f"    {comp.component_id}[{comp.name}]")
    
    # Add relationships
    for comp in network_comps:
        for dep in comp.dependencies:
            diagram.append(f"    {dep} --- {comp.component_id}")
    
    return "\n".join(diagram)


# Phase 3 Completion Node
def design_phase_complete(state: MigrationState) -> MigrationState:
    """
    Mark design phase as complete.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with design complete
    """
    try:
        state.phase_status = PhaseStatus.COMPLETED
        state.design.design_validated = True
        
        logger.info(f"Design phase completed for migration {state.migration_id}")
        
        state.messages.append({
            "role": "system",
            "content": f"Design phase complete: {len(state.design.architecture_components)} components, "
                      f"{len(state.design.diagrams)} diagrams"
        })
        
        return state
        
    except Exception as e:
        logger.error(f"Design completion failed: {str(e)}")
        state.errors.append(f"Design completion error: {str(e)}")
        return state
