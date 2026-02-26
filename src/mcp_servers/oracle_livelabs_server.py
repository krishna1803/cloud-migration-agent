"""MCP Server: Oracle Live Labs (oracle_livelabs).

Discovers Oracle Live Labs workshops and hands-on lab content relevant to
OCI migrations and cloud skill-building.

Tools (4):
  livelabs.search            - Search workshops by keyword/focus area
  livelabs.get_workshop      - Get full workshop details
  livelabs.list_focus_areas  - List available focus areas/categories
  livelabs.health            - Health check
"""
import time
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Curated Oracle Live Labs workshop catalogue
# ---------------------------------------------------------------------------

_WORKSHOPS: List[Dict[str, Any]] = [
    {
        "id": "ll-001",
        "title": "Migrate Your Applications to OCI",
        "focus_area": "Cloud Migration",
        "level": "Intermediate",
        "duration_hours": 4,
        "description": "Hands-on guide for migrating applications from AWS/Azure/GCP to OCI using tools and best practices.",
        "labs": [
            "Lab 1: Set up OCI environment and IAM",
            "Lab 2: Migrate compute instances",
            "Lab 3: Migrate object storage",
            "Lab 4: Configure networking",
            "Lab 5: Validate and cutover",
        ],
        "prerequisites": ["OCI free tier account", "Basic Linux knowledge"],
        "tags": ["migration", "aws", "azure", "gcp", "compute", "storage"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=648",
        "services": ["Compute", "Object Storage", "VCN", "IAM"],
    },
    {
        "id": "ll-002",
        "title": "OCI Fundamentals: Core Infrastructure",
        "focus_area": "OCI Foundations",
        "level": "Beginner",
        "duration_hours": 3,
        "description": "Introduction to OCI core services: VCN, Compute, Object Storage, and IAM.",
        "labs": [
            "Lab 1: Create a VCN",
            "Lab 2: Launch a Compute instance",
            "Lab 3: Create Object Storage buckets",
            "Lab 4: Configure IAM policies",
        ],
        "prerequisites": ["OCI free tier account"],
        "tags": ["fundamentals", "vcn", "compute", "storage", "iam", "beginner"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=648",
        "services": ["VCN", "Compute", "Object Storage", "IAM"],
    },
    {
        "id": "ll-003",
        "title": "Getting Started with OKE (Oracle Container Engine)",
        "focus_area": "Kubernetes",
        "level": "Intermediate",
        "duration_hours": 5,
        "description": "Deploy and manage Kubernetes workloads on OKE with node pools, autoscaling, and ingress.",
        "labs": [
            "Lab 1: Create an OKE cluster",
            "Lab 2: Deploy a sample application",
            "Lab 3: Configure autoscaling",
            "Lab 4: Set up ingress and load balancing",
            "Lab 5: Monitor with OCI Observability",
        ],
        "prerequisites": ["Docker/Kubernetes basics", "OCI account"],
        "tags": ["kubernetes", "oke", "containers", "docker", "k8s", "microservices"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=649",
        "services": ["OKE", "Load Balancer", "Container Registry", "VCN"],
    },
    {
        "id": "ll-004",
        "title": "Oracle Autonomous Database Quick Start",
        "focus_area": "Database",
        "level": "Beginner",
        "duration_hours": 2,
        "description": "Provision and use Oracle Autonomous Database (ADW and ATP) for analytics and OLTP.",
        "labs": [
            "Lab 1: Provision Autonomous Database",
            "Lab 2: Load data and run queries",
            "Lab 3: Explore auto-tuning features",
            "Lab 4: Connect from applications",
        ],
        "prerequisites": ["OCI account", "Basic SQL knowledge"],
        "tags": ["autonomous-database", "adb", "adw", "atp", "database", "sql"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=928",
        "services": ["Autonomous Database", "Object Storage"],
    },
    {
        "id": "ll-005",
        "title": "Terraform on OCI – Infrastructure as Code",
        "focus_area": "DevOps & IaC",
        "level": "Intermediate",
        "duration_hours": 4,
        "description": "Write, plan, and apply Terraform code for OCI resources. Covers state management and CI/CD integration.",
        "labs": [
            "Lab 1: Install Terraform and configure OCI provider",
            "Lab 2: Create VCN and compute resources",
            "Lab 3: Manage state with OCI Object Storage backend",
            "Lab 4: Use OCI Resource Manager",
            "Lab 5: CI/CD pipeline with Terraform",
        ],
        "prerequisites": ["Terraform basics", "OCI account"],
        "tags": ["terraform", "iac", "devops", "resource-manager", "automation"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=553",
        "services": ["Resource Manager", "VCN", "Compute", "Object Storage"],
    },
    {
        "id": "ll-006",
        "title": "Build a Data Lake on OCI",
        "focus_area": "Data & Analytics",
        "level": "Advanced",
        "duration_hours": 6,
        "description": "Design and implement a scalable data lake using Object Storage, Data Flow, and Autonomous Data Warehouse.",
        "labs": [
            "Lab 1: Set up data lake storage tiers",
            "Lab 2: Ingest data with OCI Data Integration",
            "Lab 3: Process with OCI Data Flow (Apache Spark)",
            "Lab 4: Catalog with OCI Data Catalog",
            "Lab 5: Analyze with ADW",
            "Lab 6: Visualize with OCI Analytics Cloud",
        ],
        "prerequisites": ["SQL/Python", "OCI account", "Basic Spark knowledge"],
        "tags": ["data-lake", "analytics", "big-data", "spark", "adw", "oac", "data-flow"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=741",
        "services": ["Object Storage", "Data Flow", "Data Catalog", "ADW", "OCI Analytics"],
    },
    {
        "id": "ll-007",
        "title": "OCI Security – Zero Trust with Cloud Guard",
        "focus_area": "Security",
        "level": "Intermediate",
        "duration_hours": 3,
        "description": "Implement zero-trust security posture using Cloud Guard, Security Zones, and Vault.",
        "labs": [
            "Lab 1: Enable Cloud Guard",
            "Lab 2: Configure Security Zones",
            "Lab 3: Set up OCI Vault for secrets",
            "Lab 4: Respond to security findings",
        ],
        "prerequisites": ["OCI IAM basics", "OCI account"],
        "tags": ["security", "cloud-guard", "vault", "zero-trust", "compliance", "iam"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=920",
        "services": ["Cloud Guard", "Vault", "IAM", "Security Zones"],
    },
    {
        "id": "ll-008",
        "title": "Serverless Functions on OCI",
        "focus_area": "Serverless",
        "level": "Intermediate",
        "duration_hours": 3,
        "description": "Build event-driven serverless applications using OCI Functions, Events, and API Gateway.",
        "labs": [
            "Lab 1: Create and deploy a function",
            "Lab 2: Trigger functions with Events",
            "Lab 3: Expose functions via API Gateway",
            "Lab 4: Monitor with OCI Monitoring",
        ],
        "prerequisites": ["Python/Node.js basics", "Docker", "OCI account"],
        "tags": ["serverless", "functions", "event-driven", "api-gateway", "microservices"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=522",
        "services": ["OCI Functions", "Events", "API Gateway", "Monitoring"],
    },
    {
        "id": "ll-009",
        "title": "Oracle Database Migration Service (DMS)",
        "focus_area": "Database Migration",
        "level": "Intermediate",
        "duration_hours": 4,
        "description": "Use OCI Database Migration Service to migrate Oracle and non-Oracle databases to OCI.",
        "labs": [
            "Lab 1: Set up source and target databases",
            "Lab 2: Configure DMS connection",
            "Lab 3: Create migration job",
            "Lab 4: Monitor and validate migration",
            "Lab 5: Cutover and validation",
        ],
        "prerequisites": ["Database basics", "OCI account"],
        "tags": ["database", "migration", "dms", "oracle-db", "mysql", "postgresql"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=856",
        "services": ["Database Migration Service", "Base DB Service", "ADB"],
    },
    {
        "id": "ll-010",
        "title": "OCI Observability and Monitoring",
        "focus_area": "Observability",
        "level": "Intermediate",
        "duration_hours": 3,
        "description": "Configure monitoring, logging, and tracing for OCI workloads.",
        "labs": [
            "Lab 1: Configure OCI Monitoring alarms",
            "Lab 2: Set up OCI Logging",
            "Lab 3: Enable Application Performance Monitoring",
            "Lab 4: Create dashboards",
        ],
        "prerequisites": ["OCI account", "Running OCI workloads"],
        "tags": ["monitoring", "logging", "observability", "apm", "tracing", "alerting"],
        "url": "https://apexapps.oracle.com/pls/apex/dbpm/r/livelabs/view-workshop?wid=789",
        "services": ["OCI Monitoring", "OCI Logging", "APM", "Notifications"],
    },
]

_FOCUS_AREAS = sorted({w["focus_area"] for w in _WORKSHOPS})
_ID_INDEX: Dict[str, Dict] = {w["id"]: w for w in _WORKSHOPS}


class OracleLiveLabsServer:
    """Oracle Live Labs MCP Server."""

    SERVER_NAME = "oracle_livelabs"
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

    def _score(self, workshop: Dict, query: str, focus_area: Optional[str]) -> float:
        q_words = set(re.split(r"\W+", query.lower()))
        tag_words = set(workshop.get("tags", []))
        title_words = set(re.split(r"\W+", workshop["title"].lower()))
        desc_words = set(re.split(r"\W+", workshop["description"].lower()))

        overlap = len(q_words & (tag_words | title_words | desc_words))
        score = overlap / max(len(q_words), 1)

        if focus_area and focus_area.lower() in workshop["focus_area"].lower():
            score += 0.4
        return round(min(score, 1.0), 3)

    def search(
        self,
        query: str,
        focus_area: Optional[str] = None,
        level: Optional[str] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Search Oracle Live Labs workshops.

        Args:
            query: Search string (e.g. 'kubernetes migration', 'terraform iac')
            focus_area: Optional focus area filter (e.g. 'Cloud Migration', 'Database')
            level: Optional level filter: 'Beginner', 'Intermediate', 'Advanced'
            max_results: Maximum workshops to return (default 5)
        """
        t0 = time.time()
        candidates = _WORKSHOPS

        if focus_area:
            candidates = [w for w in candidates if focus_area.lower() in w["focus_area"].lower()]
        if level:
            candidates = [w for w in candidates if level.lower() == w["level"].lower()]

        scored = [
            {**w, "_score": self._score(w, query, focus_area)}
            for w in candidates
        ]
        scored.sort(key=lambda x: x["_score"], reverse=True)
        results = scored[:max_results]
        for r in results:
            r.pop("_score", None)

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "query": query,
            "total_found": len(results),
            "workshops": results,
            "latency_ms": round(latency, 2),
        }

    def get_workshop(self, workshop_id: str) -> Dict[str, Any]:
        """Get full details of a specific Live Labs workshop.

        Args:
            workshop_id: Workshop ID (e.g. 'll-001')
        """
        t0 = time.time()
        workshop = _ID_INDEX.get(workshop_id)
        if not workshop:
            self._record((time.time() - t0) * 1000, success=False)
            return {
                "error": f"Workshop '{workshop_id}' not found",
                "available_ids": list(_ID_INDEX.keys()),
            }
        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {**workshop, "latency_ms": round(latency, 2)}

    def list_focus_areas(self) -> Dict[str, Any]:
        """List all available workshop focus areas with counts.

        Returns a summary of available focus areas and workshop counts.
        """
        t0 = time.time()
        from collections import Counter
        counts = Counter(w["focus_area"] for w in _WORKSHOPS)
        areas = [
            {"focus_area": fa, "workshop_count": counts[fa]}
            for fa in sorted(counts.keys())
        ]
        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "focus_areas": areas,
            "total_workshops": len(_WORKSHOPS),
            "latency_ms": round(latency, 2),
        }

    def health(self) -> Dict[str, Any]:
        """Health check for the Oracle Live Labs server."""
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "status": "healthy",
            "total_workshops": len(_WORKSHOPS),
            "focus_areas": _FOCUS_AREAS,
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
        }


oracle_livelabs_server = OracleLiveLabsServer()
