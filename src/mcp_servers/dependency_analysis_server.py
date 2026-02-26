"""MCP Server: Dependency Analysis (dependency_analysis).

Analyzes Terraform module dependencies, detects conflicts, and optimizes
deployment wave order for parallel execution.

Tools (6):
  analyze_terraform_dependencies  - Build dependency graph from Terraform modules
  calculate_deployment_estimate   - Estimate deployment timeline and resources
  detect_dependency_conflicts     - Find circular or conflicting dependencies
  generate_dependency_diagram     - Generate Mermaid dependency diagram
  optimize_deployment_waves       - Compute optimal parallel deployment waves
  validate_deployment_order       - Validate a proposed deployment sequence
"""
import re
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Known OCI resource deployment times (seconds, approximate)
# ---------------------------------------------------------------------------

_RESOURCE_DEPLOY_TIMES: Dict[str, int] = {
    "oci_core_vcn": 30,
    "oci_core_subnet": 20,
    "oci_core_internet_gateway": 15,
    "oci_core_nat_gateway": 15,
    "oci_core_service_gateway": 15,
    "oci_core_route_table": 10,
    "oci_core_security_list": 10,
    "oci_core_network_security_group": 10,
    "oci_core_instance": 180,
    "oci_core_volume": 60,
    "oci_load_balancer_load_balancer": 120,
    "oci_database_autonomous_database": 300,
    "oci_database_db_system": 600,
    "oci_mysql_mysql_db_system": 300,
    "oci_containerengine_cluster": 300,
    "oci_containerengine_node_pool": 240,
    "oci_objectstorage_bucket": 10,
    "oci_functions_application": 30,
    "oci_functions_function": 20,
    "oci_identity_compartment": 15,
    "oci_identity_policy": 10,
    "oci_identity_group": 10,
    "oci_kms_vault": 60,
    "oci_kms_key": 30,
}

_DEFAULT_DEPLOY_TIME = 60  # seconds for unknown resources


def _extract_deps_from_hcl(hcl: str) -> Dict[str, List[str]]:
    """Extract resource dependencies from HCL by scanning resource references."""
    # Find all resource declarations
    resource_pattern = re.compile(r'resource\s+"([\w]+)"\s+"([\w]+)"', re.MULTILINE)
    resources = {f"{m.group(1)}.{m.group(2)}" for m in resource_pattern.finditer(hcl)}

    # Find references: resource_type.resource_name.attribute
    ref_pattern = re.compile(r'(oci_[\w]+)\.([\w]+)\.[\w]+')
    deps: Dict[str, List[str]] = {r: [] for r in resources}

    # For each resource block, find which other resources it references
    block_pattern = re.compile(
        r'resource\s+"([\w]+)"\s+"([\w]+)"\s*\{(.*?)\n\}',
        re.DOTALL | re.MULTILINE,
    )
    for block_match in block_pattern.finditer(hcl):
        res_type = block_match.group(1)
        res_name = block_match.group(2)
        block_body = block_match.group(3)
        key = f"{res_type}.{res_name}"
        if key not in deps:
            deps[key] = []
        for ref in ref_pattern.finditer(block_body):
            dep_key = f"{ref.group(1)}.{ref.group(2)}"
            if dep_key in resources and dep_key != key:
                if dep_key not in deps[key]:
                    deps[key].append(dep_key)

    return deps


def _topological_sort(graph: Dict[str, List[str]]) -> Tuple[List[List[str]], bool, List[str]]:
    """Kahn's algorithm for topological sort with cycle detection.

    Returns:
        (waves, has_cycles, cycle_nodes)
    """
    in_degree: Dict[str, int] = {node: 0 for node in graph}
    for node, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[dep] = in_degree.get(dep, 0) + 1
            # The node depends on dep, so dep must come before node
            # In our graph: node -> dep means node depends on dep

    # Rebuild for proper Kahn's: reverse the dependency direction
    # deps[node] = list of nodes that node depends ON
    # We want to deploy deps first
    dependents: Dict[str, List[str]] = defaultdict(list)
    in_count: Dict[str, int] = {node: 0 for node in graph}
    for node, deps in graph.items():
        for dep in deps:
            if dep in graph:
                dependents[dep].append(node)
                in_count[node] += 1

    waves: List[List[str]] = []
    queue: deque = deque([n for n, c in in_count.items() if c == 0])
    visited: Set[str] = set()

    while queue:
        wave = list(queue)
        queue.clear()
        waves.append(wave)
        visited.update(wave)
        for node in wave:
            for dependent in dependents[node]:
                in_count[dependent] -= 1
                if in_count[dependent] == 0:
                    queue.append(dependent)

    cycle_nodes = [n for n in graph if n not in visited]
    has_cycles = len(cycle_nodes) > 0
    return waves, has_cycles, cycle_nodes


class DependencyAnalysisServer:
    """Dependency Analysis MCP Server."""

    SERVER_NAME = "dependency_analysis"
    VERSION = "1.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0.0

    def _record(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    def analyze_terraform_dependencies(
        self,
        modules: List[Dict[str, Any]],
        hcl_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a dependency graph from Terraform module definitions.

        Accepts either a list of module descriptors or raw HCL content.

        Args:
            modules: List of module dicts with keys:
                     - name (str): Module/resource name
                     - type (str): OCI resource type (e.g. 'oci_core_vcn')
                     - depends_on (list[str]): Explicit dependencies
            hcl_content: Optional raw HCL string to auto-extract dependencies

        Returns:
            Dependency graph with node metadata
        """
        t0 = time.time()

        if hcl_content:
            hcl_deps = _extract_deps_from_hcl(hcl_content)
            # Merge with explicit modules
            for full_key, deps in hcl_deps.items():
                parts = full_key.split(".", 1)
                if len(parts) == 2:
                    res_type, res_name = parts
                    existing = next((m for m in modules if m.get("name") == res_name), None)
                    if not existing:
                        modules.append({"name": res_name, "type": res_type, "depends_on": deps})
                    else:
                        existing.setdefault("depends_on", [])
                        for d in deps:
                            if d not in existing["depends_on"]:
                                existing["depends_on"].append(d)

        graph: Dict[str, List[str]] = {}
        node_meta: Dict[str, Any] = {}

        for mod in modules:
            name = mod.get("name", "unknown")
            res_type = mod.get("type", "unknown")
            deps = mod.get("depends_on", [])
            graph[name] = deps
            node_meta[name] = {
                "type": res_type,
                "depends_on": deps,
                "estimated_deploy_seconds": _RESOURCE_DEPLOY_TIMES.get(res_type, _DEFAULT_DEPLOY_TIME),
            }

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "graph": graph,
            "nodes": node_meta,
            "total_modules": len(modules),
            "total_dependencies": sum(len(d) for d in graph.values()),
            "latency_ms": round(latency, 2),
        }

    def calculate_deployment_estimate(
        self,
        graph: Dict[str, List[str]],
        node_times: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Estimate total deployment timeline given the dependency graph.

        Uses critical path analysis across parallel deployment waves.

        Args:
            graph: Dependency graph {node: [dependencies]}
            node_times: Optional per-node deploy time override in seconds

        Returns:
            Estimated sequential and parallel deployment durations
        """
        t0 = time.time()
        times = node_times or {}

        waves, has_cycles, _ = _topological_sort(graph)
        if has_cycles:
            latency = (time.time() - t0) * 1000
            self._record(latency, success=False)
            return {"error": "Cannot estimate: dependency cycles detected", "latency_ms": round(latency, 2)}

        wave_durations = []
        for wave in waves:
            max_time = max(
                times.get(n, _RESOURCE_DEPLOY_TIMES.get(n.split(".")[-1] if "." in n else n, _DEFAULT_DEPLOY_TIME))
                for n in wave
            ) if wave else 0
            wave_durations.append({"nodes": wave, "duration_seconds": max_time})

        total_parallel = sum(w["duration_seconds"] for w in wave_durations)
        total_sequential = sum(
            times.get(n, _DEFAULT_DEPLOY_TIME)
            for n in graph
        )

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "total_sequential_seconds": total_sequential,
            "total_parallel_seconds": total_parallel,
            "parallelism_savings_seconds": total_sequential - total_parallel,
            "parallelism_factor": round(total_sequential / max(total_parallel, 1), 2),
            "wave_count": len(waves),
            "wave_details": wave_durations,
            "latency_ms": round(latency, 2),
        }

    def detect_dependency_conflicts(
        self, graph: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Find circular or conflicting dependencies in the graph.

        Args:
            graph: Dependency graph {node: [dependencies]}

        Returns:
            List of detected conflicts with cycle paths
        """
        t0 = time.time()
        _, has_cycles, cycle_nodes = _topological_sort(graph)

        conflicts: List[Dict[str, Any]] = []
        if has_cycles:
            conflicts.append({
                "type": "circular_dependency",
                "severity": "CRITICAL",
                "nodes": cycle_nodes,
                "description": "Circular dependency detected — deployment will fail.",
                "recommendation": "Break the cycle by removing one dependency or introducing an intermediate resource.",
            })

        # Check for missing dependencies (references to non-existent nodes)
        missing = []
        for node, deps in graph.items():
            for dep in deps:
                if dep not in graph:
                    missing.append({"node": node, "missing_dep": dep})

        if missing:
            conflicts.append({
                "type": "missing_dependency",
                "severity": "HIGH",
                "instances": missing,
                "description": "Resources reference dependencies that are not defined in the graph.",
                "recommendation": "Add missing resources to the Terraform configuration.",
            })

        latency = (time.time() - t0) * 1000
        self._record(latency, success=not has_cycles)
        return {
            "has_conflicts": len(conflicts) > 0,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "latency_ms": round(latency, 2),
        }

    def generate_dependency_diagram(
        self,
        graph: Dict[str, List[str]],
        title: str = "OCI Deployment Dependencies",
    ) -> Dict[str, Any]:
        """Generate a Mermaid diagram visualizing resource dependencies.

        Args:
            graph: Dependency graph {node: [dependencies]}
            title: Diagram title

        Returns:
            Mermaid diagram string and metadata
        """
        t0 = time.time()
        lines = ["graph LR", f'    %% {title}']

        # Sanitize node names for Mermaid (no dots, no spaces)
        def _safe(name: str) -> str:
            return re.sub(r"[^a-zA-Z0-9_]", "_", name)

        for node, deps in graph.items():
            node_safe = _safe(node)
            if not deps:
                lines.append(f"    {node_safe}[{node}]")
            for dep in deps:
                dep_safe = _safe(dep)
                lines.append(f"    {dep_safe}[{dep}] --> {node_safe}[{node}]")

        diagram = "\n".join(lines)
        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "diagram": diagram,
            "format": "mermaid",
            "node_count": len(graph),
            "edge_count": sum(len(d) for d in graph.values()),
            "latency_ms": round(latency, 2),
        }

    def optimize_deployment_waves(
        self,
        graph: Dict[str, List[str]],
        node_times: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Compute optimal parallel deployment waves using topological sort.

        Resources in the same wave can be deployed in parallel. Resources in
        later waves depend on resources in earlier waves.

        Args:
            graph: Dependency graph {node: [dependencies]}
            node_times: Optional per-node deploy time override in seconds

        Returns:
            Ordered list of deployment waves with timing estimates
        """
        t0 = time.time()
        waves, has_cycles, cycle_nodes = _topological_sort(graph)

        if has_cycles:
            latency = (time.time() - t0) * 1000
            self._record(latency, success=False)
            return {
                "error": "Cannot optimize: circular dependencies detected",
                "cycle_nodes": cycle_nodes,
                "latency_ms": round(latency, 2),
            }

        times = node_times or {}
        optimized_waves = []
        cumulative_seconds = 0

        for i, wave in enumerate(waves):
            wave_duration = max(
                (times.get(n, _RESOURCE_DEPLOY_TIMES.get(n, _DEFAULT_DEPLOY_TIME)) for n in wave),
                default=0,
            )
            optimized_waves.append({
                "wave": i + 1,
                "resources": wave,
                "parallel_count": len(wave),
                "wave_duration_seconds": wave_duration,
                "cumulative_seconds": cumulative_seconds + wave_duration,
            })
            cumulative_seconds += wave_duration

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "wave_count": len(optimized_waves),
            "total_resources": len(graph),
            "total_duration_seconds": cumulative_seconds,
            "waves": optimized_waves,
            "latency_ms": round(latency, 2),
        }

    def validate_deployment_order(
        self,
        ordered_resources: List[str],
        graph: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Validate that a proposed deployment sequence respects all dependencies.

        Args:
            ordered_resources: Proposed deployment order (list of resource names)
            graph: Dependency graph {node: [dependencies]}

        Returns:
            Validation result with any ordering violations
        """
        t0 = time.time()
        violations: List[Dict[str, Any]] = []
        deployed: Set[str] = set()

        for i, resource in enumerate(ordered_resources):
            deps = graph.get(resource, [])
            for dep in deps:
                if dep in graph and dep not in deployed:
                    violations.append({
                        "resource": resource,
                        "position": i,
                        "missing_dependency": dep,
                        "description": f"'{resource}' at position {i} depends on '{dep}' which has not been deployed yet.",
                    })
            deployed.add(resource)

        # Check for resources in graph not in ordered list
        missing_from_order = [n for n in graph if n not in ordered_resources]
        if missing_from_order:
            violations.append({
                "type": "incomplete_ordering",
                "missing_resources": missing_from_order,
                "description": "Some resources in the dependency graph are not in the deployment order.",
            })

        is_valid = len(violations) == 0
        latency = (time.time() - t0) * 1000
        self._record(latency, success=is_valid)
        return {
            "is_valid": is_valid,
            "violation_count": len(violations),
            "violations": violations,
            "resources_checked": len(ordered_resources),
            "latency_ms": round(latency, 2),
        }

    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "status": "healthy",
            "known_resource_types": len(_RESOURCE_DEPLOY_TIMES),
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
        }


dependency_analysis_server = DependencyAnalysisServer()
