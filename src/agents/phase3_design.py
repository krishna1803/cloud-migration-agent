"""
Phase 3: Design - Agent nodes for formal architecture modeling.

This phase creates formal architecture models with components,
dependencies, and deployment sequences.
"""

import json
import time
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
from src.utils.logger import logger, log_node_entry, log_node_exit, log_llm_call, log_error


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
        t0 = time.time()
        log_node_entry(state.migration_id, "design", "formal_architecture_modeling", {
            "mappings_count": len(state.analysis.service_mappings),
            "sizing_count": len(state.analysis.sizing_recommendations),
            "target_design_chars": len(str(state.messages[-1]["content"] if state.messages else "")),
        })

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
        prompt_inputs = {
            "mappings": str([m.dict() for m in state.analysis.service_mappings]),
            "sizing": str([s.dict() for s in state.analysis.sizing_recommendations]),
            "target_design": str(state.messages[-1]["content"] if state.messages else ""),
        }

        t_llm = time.time()
        components_data = chain.invoke(prompt_inputs)
        llm_ms = (time.time() - t_llm) * 1000

        comp_names = [c.get("name", "?") for c in (components_data or [])[:5]]
        log_llm_call(
            state.migration_id,
            "formal_architecture_modeling",
            prompt_preview=(
                f"mappings={len(state.analysis.service_mappings)}, "
                f"sizing={len(state.analysis.sizing_recommendations)}"
            ),
            response_preview=f"{len(components_data)} components: {comp_names}",
            duration_ms=llm_ms,
        )

        # Create component objects
        for comp_data in components_data:
            component = ArchitectureComponent(**comp_data)
            state.design.architecture_components.append(component)

        comp_types: dict = {}
        for c in state.design.architecture_components:
            comp_types[c.component_type] = comp_types.get(c.component_type, 0) + 1

        log_node_exit(state.migration_id, "design", "formal_architecture_modeling", {
            "components_created": len(components_data),
            "component_types": str(comp_types),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "architecture_modeling_error", str(e), phase="design")
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
        t0 = time.time()
        log_node_entry(state.migration_id, "design", "component_definition", {
            "component_count": len(state.design.architecture_components),
        })

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
            t_llm = time.time()
            detailed_config = chain.invoke({
                "component": component.name,
                "comp_type": component.component_type,
                "oci_service": component.oci_service,
            })
            llm_ms = (time.time() - t_llm) * 1000

            log_llm_call(
                state.migration_id,
                "component_definition",
                prompt_preview=(
                    f"component={component.name}, type={component.component_type}, "
                    f"service={component.oci_service}"
                ),
                response_preview=f"config_keys={list(detailed_config.keys())[:8]}",
                duration_ms=llm_ms,
            )

            # Update component configuration
            component.configuration.update(detailed_config)

        log_node_exit(state.migration_id, "design", "component_definition", {
            "components_enriched": len(state.design.architecture_components),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "component_definition_error", str(e), phase="design")
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
        t0 = time.time()
        log_node_entry(state.migration_id, "design", "dependency_mapping", {
            "component_count": len(state.design.architecture_components),
            "component_ids": str([c.component_id for c in state.design.architecture_components[:8]]),
        })

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
        t_llm = time.time()
        dependencies = chain.invoke({
            "components": str([c.dict() for c in state.design.architecture_components])
        })
        llm_ms = (time.time() - t_llm) * 1000

        total_edges = sum(len(v) for v in dependencies.values())
        log_llm_call(
            state.migration_id,
            "dependency_mapping",
            prompt_preview=f"components={len(state.design.architecture_components)}",
            response_preview=(
                f"dependency_map: {len(dependencies)} nodes, {total_edges} total edges"
            ),
            duration_ms=llm_ms,
        )

        # Update component dependencies and state
        state.design.component_dependencies = dependencies

        for component in state.design.architecture_components:
            if component.component_id in dependencies:
                component.dependencies = dependencies[component.component_id]

        log_node_exit(state.migration_id, "design", "dependency_mapping", {
            "components_mapped": len(dependencies),
            "total_dependency_edges": total_edges,
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "dependency_mapping_error", str(e), phase="design")
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
        t0 = time.time()
        log_node_entry(state.migration_id, "design", "topological_sort_deployment", {
            "component_count": len(state.design.architecture_components),
            "dependency_pairs": len(state.design.component_dependencies),
        })

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
            log_node_exit(state.migration_id, "design", "topological_sort_deployment", {
                "result": "CYCLE_DETECTED",
                "cycles": str(cycles[:3]),
            }, duration_ms=(time.time() - t0) * 1000)
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

        log_node_exit(state.migration_id, "design", "topological_sort_deployment", {
            "deployment_sequence_length": len(deployment_order),
            "first_5": str(deployment_order[:5]),
            "last_5": str(deployment_order[-5:]),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "topological_sort_error", str(e), phase="design")
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
        t0 = time.time()
        log_node_entry(state.migration_id, "design", "diagram_generation", {
            "component_count": len(state.design.architecture_components),
            "deployment_sequence_length": len(state.design.deployment_sequence),
        })

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

        diagram_types = [d.diagram_type for d in state.design.diagrams]
        log_node_exit(state.migration_id, "design", "diagram_generation", {
            "diagrams_generated": len(state.design.diagrams),
            "diagram_types": str(diagram_types),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "diagram_generation_error", str(e), phase="design")
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
        t0 = time.time()
        log_node_entry(state.migration_id, "design", "design_phase_complete", {
            "components": len(state.design.architecture_components),
            "diagrams": len(state.design.diagrams),
            "deployment_sequence_length": len(state.design.deployment_sequence),
        })

        state.phase_status = PhaseStatus.COMPLETED
        state.design.design_validated = True

        completion_msg = (
            f"Design phase complete: {len(state.design.architecture_components)} components, "
            f"{len(state.design.diagrams)} diagrams"
        )
        state.messages.append({"role": "system", "content": completion_msg})

        log_node_exit(state.migration_id, "design", "design_phase_complete", {
            "phase_status": "COMPLETED",
            "design_validated": True,
            "summary": completion_msg,
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "design_complete_error", str(e), phase="design")
        state.errors.append(f"Design completion error: {str(e)}")
        return state
