"""MCP Server: Oracle Architecture Hub (oracle_archhub).

Searches Oracle Architecture Hub for reference architectures, solution assets,
and design patterns relevant to OCI migrations.

Tools (6):
  archhub.search             - Search architecture hub by keyword/workload
  archhub.get_page           - Get a specific architecture page details
  archhub.get_assets         - Get associated Terraform/diagram assets
  archhub.get_related        - Get related architectures
  archhub.extract_architecture - Extract structured architecture details
  archhub.health             - Health check
"""
import time
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Curated Oracle Architecture Hub catalogue (offline knowledge base)
# Real deployments can call https://docs.oracle.com/solutions/ via HTTP.
# ---------------------------------------------------------------------------

_ARCH_CATALOGUE: List[Dict[str, Any]] = [
    {
        "id": "arch-001",
        "title": "Deploy a highly available three-tier web app in OCI",
        "category": "Web Application",
        "description": "Deploys a three-tier web application (LB + App + DB) across multiple ADs.",
        "services": ["Load Balancer", "Compute", "Autonomous Database", "VCN", "WAF"],
        "tags": ["three-tier", "ha", "web", "app", "load-balancer", "database"],
        "complexity": "medium",
        "terraform_module": "oracle-quickstart/oci-arch-web-app-mds",
        "doc_url": "https://docs.oracle.com/solutions/deploy-highly-available-web-app",
        "diagram_url": "https://docs.oracle.com/solutions/deploy-highly-available-web-app/img/architecture.png",
    },
    {
        "id": "arch-002",
        "title": "OCI Landing Zone",
        "category": "Foundation",
        "description": "Enterprise-grade landing zone with compartments, IAM, VCN, and logging.",
        "services": ["Compartments", "IAM", "VCN", "Cloud Guard", "Logging", "Budget"],
        "tags": ["landing-zone", "foundation", "governance", "security", "enterprise"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-cis-landingzone",
        "doc_url": "https://docs.oracle.com/solutions/cis-oci-benchmark",
        "diagram_url": "https://docs.oracle.com/solutions/cis-oci-benchmark/img/architecture.png",
    },
    {
        "id": "arch-003",
        "title": "Deploy OKE cluster with Kubernetes workloads",
        "category": "Kubernetes",
        "description": "Production-ready OKE cluster with node pools, ingress, and monitoring.",
        "services": ["OKE", "VCN", "Load Balancer", "Container Registry", "Object Storage"],
        "tags": ["kubernetes", "oke", "containers", "k8s", "microservices"],
        "complexity": "medium",
        "terraform_module": "oracle-quickstart/oci-arch-oke",
        "doc_url": "https://docs.oracle.com/solutions/oci-oke",
        "diagram_url": "https://docs.oracle.com/solutions/oci-oke/img/architecture.png",
    },
    {
        "id": "arch-004",
        "title": "Migrate Oracle Database to OCI Base Database Service",
        "category": "Database Migration",
        "description": "Lift-and-shift Oracle DB to Base DB Service with Data Guard for HA.",
        "services": ["Base DB Service", "VCN", "Data Guard", "Object Storage", "DMS"],
        "tags": ["database", "oracle-db", "migration", "data-guard", "lift-shift"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-arch-db-migration",
        "doc_url": "https://docs.oracle.com/solutions/oci-db-migration",
        "diagram_url": "https://docs.oracle.com/solutions/oci-db-migration/img/architecture.png",
    },
    {
        "id": "arch-005",
        "title": "Build a data lake on OCI Object Storage",
        "category": "Data & Analytics",
        "description": "Scalable data lake using Object Storage, Data Flow, and Data Catalog.",
        "services": ["Object Storage", "Data Flow", "Data Catalog", "OCI Analytics", "ADB"],
        "tags": ["data-lake", "analytics", "big-data", "data-flow", "object-storage"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-arch-data-lake",
        "doc_url": "https://docs.oracle.com/solutions/oci-data-lake",
        "diagram_url": "https://docs.oracle.com/solutions/oci-data-lake/img/architecture.png",
    },
    {
        "id": "arch-006",
        "title": "Serverless event-driven architecture with OCI Functions",
        "category": "Serverless",
        "description": "Event-driven microservices using OCI Functions, Events, and Streaming.",
        "services": ["OCI Functions", "Events", "Streaming", "API Gateway", "Object Storage"],
        "tags": ["serverless", "functions", "event-driven", "streaming", "microservices"],
        "complexity": "medium",
        "terraform_module": "oracle-quickstart/oci-arch-functions",
        "doc_url": "https://docs.oracle.com/solutions/oci-functions-event-driven",
        "diagram_url": "https://docs.oracle.com/solutions/oci-functions-event-driven/img/architecture.png",
    },
    {
        "id": "arch-007",
        "title": "Multi-region active-active DR with Traffic Management",
        "category": "Disaster Recovery",
        "description": "Active-active DR across two OCI regions using Traffic Management and DRG.",
        "services": ["Traffic Management", "DRG", "VCN", "Load Balancer", "ADB", "Object Storage"],
        "tags": ["dr", "disaster-recovery", "multi-region", "active-active", "high-availability"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-arch-dr",
        "doc_url": "https://docs.oracle.com/solutions/oci-dr-active-active",
        "diagram_url": "https://docs.oracle.com/solutions/oci-dr-active-active/img/architecture.png",
    },
    {
        "id": "arch-008",
        "title": "AI/ML platform on OCI with Data Science",
        "category": "AI & Machine Learning",
        "description": "End-to-end ML platform with Data Science, GPU compute, and model deployment.",
        "services": ["OCI Data Science", "GPU Compute", "Object Storage", "Functions", "API Gateway"],
        "tags": ["ai", "ml", "machine-learning", "data-science", "gpu", "model-serving"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-arch-data-science",
        "doc_url": "https://docs.oracle.com/solutions/oci-data-science",
        "diagram_url": "https://docs.oracle.com/solutions/oci-data-science/img/architecture.png",
    },
    {
        "id": "arch-009",
        "title": "Autonomous Data Warehouse with Analytics Cloud",
        "category": "Data Warehouse",
        "description": "Enterprise DWH using ADW + OAC with self-service analytics.",
        "services": ["Autonomous Data Warehouse", "OCI Analytics", "Data Integration", "Object Storage"],
        "tags": ["data-warehouse", "adw", "analytics", "oac", "bi", "reporting"],
        "complexity": "medium",
        "terraform_module": "oracle-quickstart/oci-arch-adw-oac",
        "doc_url": "https://docs.oracle.com/solutions/adw-oac",
        "diagram_url": "https://docs.oracle.com/solutions/adw-oac/img/architecture.png",
    },
    {
        "id": "arch-010",
        "title": "Deploy microservices mesh with OCI Service Mesh",
        "category": "Microservices",
        "description": "Service mesh for microservices on OKE with traffic control and observability.",
        "services": ["OKE", "OCI Service Mesh", "Load Balancer", "Container Registry", "Logging"],
        "tags": ["microservices", "service-mesh", "oke", "observability", "traffic-management"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-arch-service-mesh",
        "doc_url": "https://docs.oracle.com/solutions/oci-service-mesh",
        "diagram_url": "https://docs.oracle.com/solutions/oci-service-mesh/img/architecture.png",
    },
    {
        "id": "arch-011",
        "title": "Message queue workers with OCI Streaming and Queue",
        "category": "Messaging",
        "description": "Scalable message processing using OCI Queue Service and worker compute.",
        "services": ["OCI Queue", "Streaming", "Compute", "Functions", "Object Storage"],
        "tags": ["queue", "messaging", "streaming", "worker", "async", "event"],
        "complexity": "medium",
        "terraform_module": "oracle-quickstart/oci-arch-queue-workers",
        "doc_url": "https://docs.oracle.com/solutions/oci-queue-workers",
        "diagram_url": "https://docs.oracle.com/solutions/oci-queue-workers/img/architecture.png",
    },
    {
        "id": "arch-012",
        "title": "HPC cluster with batch workloads on OCI",
        "category": "HPC",
        "description": "High-performance computing cluster using BM shapes and RDMA networking.",
        "services": ["BM.HPC", "RDMA Cluster Network", "Object Storage", "File Storage", "VCN"],
        "tags": ["hpc", "batch", "high-performance", "rdma", "compute", "simulation"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-arch-hpc",
        "doc_url": "https://docs.oracle.com/solutions/oci-hpc",
        "diagram_url": "https://docs.oracle.com/solutions/oci-hpc/img/architecture.png",
    },
    {
        "id": "arch-013",
        "title": "Migrate AWS workloads to OCI – phased approach",
        "category": "Cloud Migration",
        "description": "Structured approach to migrating AWS workloads to OCI in phases.",
        "services": ["Compute", "VCN", "Object Storage", "Database Migration Service", "FastConnect"],
        "tags": ["aws", "migration", "lift-shift", "phased", "cloud-migration"],
        "complexity": "high",
        "terraform_module": "oracle-quickstart/oci-arch-aws-migration",
        "doc_url": "https://docs.oracle.com/solutions/aws-oci-migration",
        "diagram_url": "https://docs.oracle.com/solutions/aws-oci-migration/img/architecture.png",
    },
]

_ID_INDEX: Dict[str, Dict] = {a["id"]: a for a in _ARCH_CATALOGUE}


class OracleArchHubServer:
    """Oracle Architecture Hub MCP Server."""

    SERVER_NAME = "oracle_archhub"
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

    def _score(self, arch: Dict, query: str, workload_type: Optional[str]) -> float:
        """Simple relevance score for keyword matching."""
        q_words = set(re.split(r"\W+", query.lower()))
        tag_words = set(arch.get("tags", []))
        title_words = set(re.split(r"\W+", arch["title"].lower()))
        desc_words = set(re.split(r"\W+", arch["description"].lower()))

        overlap = len(q_words & (tag_words | title_words | desc_words))
        score = overlap / max(len(q_words), 1)

        if workload_type and workload_type.lower() in arch.get("tags", []):
            score += 0.3
        return round(min(score, 1.0), 3)

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        workload_type: Optional[str] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Search Oracle Architecture Hub for reference architectures.

        Args:
            query: Natural-language search string (e.g. 'three-tier web app')
            category: Optional category filter (e.g. 'Web Application', 'Kubernetes')
            workload_type: Optional workload hint (e.g. 'database', 'microservices')
            max_results: Maximum results to return (default 5)
        """
        t0 = time.time()
        candidates = _ARCH_CATALOGUE

        if category:
            candidates = [a for a in candidates if category.lower() in a["category"].lower()]

        scored = [
            {**a, "_score": self._score(a, query, workload_type)}
            for a in candidates
        ]
        scored.sort(key=lambda x: x["_score"], reverse=True)
        results = scored[:max_results]

        # Remove internal _score key
        for r in results:
            r.pop("_score", None)

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "query": query,
            "total_found": len(results),
            "results": results,
            "latency_ms": round(latency, 2),
        }

    def get_page(self, arch_id: str) -> Dict[str, Any]:
        """Get full details of a specific architecture page by ID.

        Args:
            arch_id: Architecture ID (e.g. 'arch-001')
        """
        t0 = time.time()
        arch = _ID_INDEX.get(arch_id)
        if not arch:
            latency = (time.time() - t0) * 1000
            self._record(latency, success=False)
            return {"error": f"Architecture '{arch_id}' not found", "available_ids": list(_ID_INDEX.keys())}

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {**arch, "latency_ms": round(latency, 2)}

    def get_assets(self, arch_id: str) -> Dict[str, Any]:
        """Get Terraform modules and diagram assets for an architecture.

        Args:
            arch_id: Architecture ID (e.g. 'arch-001')
        """
        t0 = time.time()
        arch = _ID_INDEX.get(arch_id)
        if not arch:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": f"Architecture '{arch_id}' not found"}

        assets = {
            "arch_id": arch_id,
            "terraform_module": arch.get("terraform_module"),
            "terraform_registry_url": f"https://registry.terraform.io/modules/{arch.get('terraform_module', '')}",
            "diagram_url": arch.get("diagram_url"),
            "doc_url": arch.get("doc_url"),
            "assets": [
                {"type": "terraform_module", "url": f"https://registry.terraform.io/modules/{arch.get('terraform_module', '')}", "format": "HCL"},
                {"type": "architecture_diagram", "url": arch.get("diagram_url", ""), "format": "PNG"},
                {"type": "documentation", "url": arch.get("doc_url", ""), "format": "HTML"},
            ],
        }
        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {**assets, "latency_ms": round(latency, 2)}

    def get_related(self, arch_id: str, max_results: int = 3) -> Dict[str, Any]:
        """Get architectures related to a given one (same category or shared tags).

        Args:
            arch_id: Architecture ID to find relatives for
            max_results: Maximum related architectures to return
        """
        t0 = time.time()
        arch = _ID_INDEX.get(arch_id)
        if not arch:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": f"Architecture '{arch_id}' not found"}

        target_tags = set(arch.get("tags", []))
        target_cat = arch["category"]

        related = []
        for other in _ARCH_CATALOGUE:
            if other["id"] == arch_id:
                continue
            shared_tags = len(set(other.get("tags", [])) & target_tags)
            same_cat = 1 if other["category"] == target_cat else 0
            score = shared_tags + same_cat * 2
            if score > 0:
                related.append({**other, "_score": score})

        related.sort(key=lambda x: x["_score"], reverse=True)
        for r in related:
            r.pop("_score", None)

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "arch_id": arch_id,
            "related": related[:max_results],
            "latency_ms": round(latency, 2),
        }

    def extract_architecture(self, arch_id: str) -> Dict[str, Any]:
        """Extract structured architecture details: components, relationships, constraints.

        Args:
            arch_id: Architecture ID to extract details from
        """
        t0 = time.time()
        arch = _ID_INDEX.get(arch_id)
        if not arch:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": f"Architecture '{arch_id}' not found"}

        # Build structured component breakdown
        components = [
            {
                "service": svc,
                "role": "primary" if i == 0 else "supporting",
                "oci_category": _svc_category(svc),
            }
            for i, svc in enumerate(arch.get("services", []))
        ]

        extracted = {
            "arch_id": arch_id,
            "title": arch["title"],
            "category": arch["category"],
            "complexity": arch["complexity"],
            "components": components,
            "component_count": len(components),
            "primary_service": arch["services"][0] if arch["services"] else None,
            "tags": arch.get("tags", []),
            "migration_suitability": _migration_suitability(arch),
            "terraform_module": arch.get("terraform_module"),
            "doc_url": arch.get("doc_url"),
        }
        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {**extracted, "latency_ms": round(latency, 2)}

    def health(self) -> Dict[str, Any]:
        """Health check for the Oracle Architecture Hub server."""
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "status": "healthy",
            "total_architectures": len(_ARCH_CATALOGUE),
            "categories": list({a["category"] for a in _ARCH_CATALOGUE}),
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
        }


def _svc_category(service: str) -> str:
    """Return OCI service category from service name."""
    svc = service.lower()
    if any(k in svc for k in ["compute", "instance", "gpu", "bm.", "vm."]):
        return "Compute"
    if any(k in svc for k in ["database", "adb", "autonomous", "mysql", "db system"]):
        return "Database"
    if any(k in svc for k in ["storage", "bucket", "file storage"]):
        return "Storage"
    if any(k in svc for k in ["vcn", "subnet", "load balancer", "drg", "fastconnect", "dns", "waf"]):
        return "Networking"
    if any(k in svc for k in ["oke", "container", "registry"]):
        return "Containers"
    if any(k in svc for k in ["function", "api gateway", "event", "queue", "streaming"]):
        return "Serverless"
    if any(k in svc for k in ["iam", "compartment", "cloud guard", "vault", "security"]):
        return "Security"
    if any(k in svc for k in ["analytics", "data science", "data flow", "data catalog", "data integration"]):
        return "Analytics"
    return "Other"


def _migration_suitability(arch: Dict) -> Dict[str, Any]:
    tags = set(arch.get("tags", []))
    return {
        "aws_migration": "aws" in tags or "migration" in tags or "lift-shift" in tags,
        "azure_migration": "azure" in tags or "migration" in tags,
        "gcp_migration": "gcp" in tags or "migration" in tags,
        "greenfield": "landing-zone" in tags or "foundation" in tags,
        "lift_and_shift": "lift-shift" in tags or "migration" in tags,
        "re_architect": arch["complexity"] == "high" and "microservices" in tags,
    }


oracle_archhub_server = OracleArchHubServer()
