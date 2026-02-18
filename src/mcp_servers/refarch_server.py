"""MCP Server 5: OCI Reference Architectures.

Curated OCI Architecture Center patterns with Terraform snippets,
component lists, and workload-matching logic.

References:
  https://docs.oracle.com/solutions/
  https://docs.oracle.com/en-us/iaas/Content/General/Reference/aqswhitepapers.htm
"""
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# TEMPLATE CATALOGUE
# Each template mirrors a real OCI Architecture Center solution.
# ---------------------------------------------------------------------------
TEMPLATES: List[Dict[str, Any]] = [
    # ── FOUNDATION ────────────────────────────────────────────────────────────
    {
        "template_id":   "oci-landing-zone-v2",
        "name":          "OCI Landing Zone (CIS Benchmark)",
        "category":      "Foundation",
        "description":   (
            "Enterprise-grade, CIS OCI Foundations Benchmark-compliant multi-account foundation. "
            "Deploys compartment hierarchy, IAM policies, VCN, Security Lists, NSGs, "
            "bastion, audit logging, Cloud Guard, and budget alerts."
        ),
        "complexity":    "medium",
        "oci_services":  ["VCN", "IAM", "Cloud Guard", "Bastion", "Audit", "Budget"],
        "components":    [
            "VCN (3 subnets: public, private-app, private-db)",
            "Internet Gateway + NAT Gateway + Service Gateway",
            "IAM Compartments: Network, Security, App, DB",
            "Security List + NSG per tier",
            "OCI Bastion Service",
            "Cloud Guard (CIS recipe)",
            "Vault (AES-256 master key)",
            "Budget + Alert rule",
            "Object Storage bucket for audit logs",
        ],
        "source_providers": ["AWS", "Azure", "GCP", "On-Premises"],
        "match_keywords": ["landing zone", "foundation", "governance", "compliance",
                           "security", "cis", "organization", "multi-account"],
        "terraform_module": "github.com/oracle-terraform-modules/terraform-oci-landing-zones",
        "architecture_url": "https://docs.oracle.com/en/solutions/cis-oci-benchmark/",
        "diagram_mermaid": """
graph TB
    Internet --> IGW[Internet Gateway]
    IGW --> LB[Load Balancer - Public Subnet]
    LB --> APP[App Tier - Private Subnet]
    APP --> DB[DB Tier - Private Subnet]
    APP --> SG[Service Gateway]
    SG --> OCI_Services[OCI Services]
    DB --> BV[Block Volumes]
    subgraph VCN
        LB
        APP
        DB
    end
    Cloud_Guard[Cloud Guard] -.-> VCN
    Vault[Vault] -.-> APP
    Bastion[Bastion] -.-> APP
""",
        "estimated_monthly_cost_usd": 150,
        "tags": ["cis", "security", "foundation", "enterprise"],
    },
    # ── WEB APPLICATION ───────────────────────────────────────────────────────
    {
        "template_id":   "oci-three-tier-web-app",
        "name":          "Three-Tier Web Application",
        "category":      "Web Application",
        "description":   (
            "Classic presentation/logic/data tier pattern on OCI. "
            "Flexible Load Balancer fronts multiple Compute instances in an Instance Pool "
            "across two ADs. Oracle Autonomous Database in the private tier. "
            "Suitable for e-commerce, SaaS portals, CMS platforms."
        ),
        "complexity":    "low",
        "oci_services":  ["Load Balancer", "Compute", "Autonomous Database", "Object Storage", "VCN"],
        "components":    [
            "Flexible Load Balancer (public subnet)",
            "Instance Pool: VM.Standard.E4.Flex (2 OCPUs, 16 GB) × 2 ADs",
            "Autonomous Transaction Processing (ATP) — 2 OCPUs, 1 TB storage",
            "Object Storage bucket for static assets (CDN-backed)",
            "VCN with 3 subnets (public, app-private, db-private)",
            "NSG rules per tier",
        ],
        "source_providers": ["AWS", "Azure", "GCP", "On-Premises"],
        "match_keywords": ["web", "app", "three-tier", "load balancer", "database",
                           "php", "node", "spring", "django", "rails", "wordpress"],
        "terraform_module": "oracle-terraform-modules/terraform-oci-base",
        "architecture_url": "https://docs.oracle.com/en/solutions/deploy-three-tier-web-app-oci/",
        "diagram_mermaid": """
graph TB
    Internet --> FLB[Flexible Load Balancer]
    FLB --> WEB1[Web/App VM AD1]
    FLB --> WEB2[Web/App VM AD2]
    WEB1 --> ATP[Autonomous DB ATP]
    WEB2 --> ATP
    WEB1 --> OS[Object Storage CDN]
    WEB2 --> OS
""",
        "estimated_monthly_cost_usd": 350,
        "tags": ["web", "app-server", "atp", "instance-pool"],
    },
    # ── MICROSERVICES / OKE ───────────────────────────────────────────────────
    {
        "template_id":   "oci-microservices-oke",
        "name":          "Microservices on OKE (Oracle Container Engine)",
        "category":      "Kubernetes",
        "description":   (
            "Cloud-native microservices reference architecture on OKE. "
            "API Gateway routes external traffic to OKE services. "
            "OCIR stores container images. OCI DevOps automates CI/CD. "
            "OCI Streaming provides event backbone. Vault manages secrets."
        ),
        "complexity":    "high",
        "oci_services":  ["OKE", "API Gateway", "OCIR", "OCI DevOps", "OCI Streaming",
                          "Vault", "Load Balancer", "VCN"],
        "components":    [
            "OKE Cluster (Kubernetes 1.29, 3 worker nodes VM.Standard.E4.Flex)",
            "OCI Container Registry (OCIR)",
            "OCI API Gateway (REST + WebSocket)",
            "OCI DevOps: Build + Deploy Pipelines",
            "OCI Streaming (event backbone, Kafka-compatible)",
            "OCI Queue (async task queues)",
            "Vault (Kubernetes secrets integration)",
            "Autonomous DB (app data store)",
            "OCI Monitoring + Logging",
        ],
        "source_providers": ["AWS", "Azure", "GCP"],
        "match_keywords": ["kubernetes", "k8s", "eks", "aks", "gke", "microservices",
                           "containers", "docker", "helm", "istio", "service mesh",
                           "api gateway", "devops", "ci/cd"],
        "terraform_module": "oracle-terraform-modules/terraform-oci-oke",
        "architecture_url": "https://docs.oracle.com/en/solutions/microservices-oke/",
        "diagram_mermaid": """
graph TB
    Internet --> APIGW[API Gateway]
    APIGW --> OKE[OKE Cluster]
    OKE --> SVC1[Service A Pod]
    OKE --> SVC2[Service B Pod]
    OKE --> SVC3[Service C Pod]
    SVC1 --> Stream[OCI Streaming]
    SVC2 --> Stream
    SVC3 --> ATP[Autonomous DB]
    OCIR[Container Registry] --> OKE
    DevOps[OCI DevOps CI/CD] --> OCIR
    Vault[Vault Secrets] -.-> OKE
""",
        "estimated_monthly_cost_usd": 800,
        "tags": ["kubernetes", "containers", "microservices", "cloud-native", "devops"],
    },
    # ── DATA PLATFORM ─────────────────────────────────────────────────────────
    {
        "template_id":   "oci-data-platform",
        "name":          "OCI Data Lakehouse Platform",
        "category":      "Data & Analytics",
        "description":   (
            "Modern data platform combining Oracle ADW, OCI Data Integration, "
            "OCI Data Flow (Spark), OCI Data Catalog, and Oracle Analytics Cloud. "
            "Implements medallion architecture: raw → bronze → silver → gold in Object Storage."
        ),
        "complexity":    "high",
        "oci_services":  ["ADW", "Object Storage", "OCI Data Integration",
                          "OCI Data Flow", "OAC", "OCI Data Catalog"],
        "components":    [
            "Autonomous Data Warehouse (ADW) — 4 OCPUs, 2 TB",
            "Object Storage: raw / bronze / silver / gold zones",
            "OCI Data Integration (ETL pipelines)",
            "OCI Data Flow (Apache Spark 3.x managed)",
            "OCI Data Catalog (metadata management)",
            "Oracle Analytics Cloud — Professional 4 OCPUs",
            "OCI Streaming (data ingestion)",
            "Golden Gate (real-time CDC from source DB)",
        ],
        "source_providers": ["AWS", "Azure", "GCP", "On-Premises"],
        "match_keywords": ["data warehouse", "analytics", "bigquery", "redshift",
                           "synapse", "etl", "spark", "hadoop", "data lake",
                           "business intelligence", "bi", "reporting", "olap"],
        "terraform_module": "oracle-terraform-modules/terraform-oci-data-platform",
        "architecture_url": "https://docs.oracle.com/en/solutions/data-lakehouse/",
        "diagram_mermaid": """
graph LR
    Sources[Source Systems] --> Stream[OCI Streaming]
    Sources --> GG[GoldenGate CDC]
    Stream --> Raw[Object Storage Raw]
    GG --> Raw
    Raw --> DI[Data Integration ETL]
    DI --> Bronze[Object Storage Bronze]
    DF[Data Flow Spark] --> Silver[Object Storage Silver]
    Bronze --> DF
    Silver --> ADW[Autonomous DW]
    ADW --> OAC[Oracle Analytics Cloud]
    Catalog[Data Catalog] -.-> ADW
""",
        "estimated_monthly_cost_usd": 1500,
        "tags": ["data-lake", "analytics", "adw", "spark", "etl"],
    },
    # ── DISASTER RECOVERY ─────────────────────────────────────────────────────
    {
        "template_id":   "oci-disaster-recovery",
        "name":          "OCI Cross-Region Disaster Recovery",
        "category":      "Resilience",
        "description":   (
            "Active-passive DR across two OCI regions using OCI Full Stack DR. "
            "Automates failover of Compute, Block Volumes, Autonomous DB, and Object Storage. "
            "RTO target < 15 minutes; RPO depends on replication schedule (typically < 1 hr)."
        ),
        "complexity":    "high",
        "oci_services":  ["Full Stack DR", "Object Storage", "Block Volume Replication",
                          "Autonomous DB", "DRG", "VPN Connect / FastConnect"],
        "components":    [
            "Primary Region: VCN + 3-tier app",
            "DR Region: identical VCN topology (warm standby)",
            "OCI Full Stack DR Plan (automated orchestration)",
            "Block Volume Cross-Region Replication",
            "Autonomous DB Data Guard (local + remote)",
            "Object Storage Cross-Region Replication",
            "DRG v2 + Remote Peering (inter-region)",
            "DNS traffic steering (health-check failover)",
        ],
        "source_providers": ["AWS", "Azure", "GCP", "On-Premises"],
        "match_keywords": ["disaster recovery", "dr", "business continuity", "rpo", "rto",
                           "ha", "high availability", "multi-region", "backup", "failover"],
        "terraform_module": "oracle-quickstart/oci-fullstackdr",
        "architecture_url": "https://docs.oracle.com/en/solutions/cross-region-dr/",
        "diagram_mermaid": """
graph LR
    subgraph Primary[Primary Region - us-ashburn-1]
        APP1[App Tier]
        DB1[Autonomous DB Primary]
        BV1[Block Volumes]
    end
    subgraph DR[DR Region - us-phoenix-1]
        APP2[App Tier standby]
        DB2[Autonomous DB Standby]
        BV2[Block Volumes Replica]
    end
    DB1 -->|Data Guard| DB2
    BV1 -->|Cross-Region Replication| BV2
    FSDR[Full Stack DR] -->|Orchestrates| Primary
    FSDR -->|Orchestrates| DR
    DNS[OCI DNS Health-Check] -->|Failover| DR
""",
        "estimated_monthly_cost_usd": 600,
        "tags": ["dr", "resilience", "ha", "full-stack-dr"],
    },
    # ── HPC ───────────────────────────────────────────────────────────────────
    {
        "template_id":   "oci-hpc-cluster",
        "name":          "OCI HPC Cluster (RDMA Networking)",
        "category":      "HPC",
        "description":   (
            "High-performance computing cluster using OCI bare metal RDMA-enabled instances. "
            "Cluster networking provides 100 Gbps low-latency interconnect. "
            "Suitable for CFD, FEA, genomics, seismic processing."
        ),
        "complexity":    "high",
        "oci_services":  ["Compute (BM)", "Cluster Network", "File Storage", "Object Storage",
                          "Bastion", "VCN"],
        "components":    [
            "BM.Optimized3.36 (36 OCPUs, 512 GB, 100 Gbps RDMA) — compute nodes",
            "Cluster Network (RDMA, < 2 μs latency)",
            "File Storage (shared /home and /scratch)",
            "Object Storage (input/output data)",
            "Head node: VM.Standard.E4.Flex (bastion + job scheduler)",
            "SLURM / OpenPBS job scheduler",
            "Autoscaling (add BM nodes on demand)",
        ],
        "source_providers": ["AWS", "Azure", "GCP", "On-Premises"],
        "match_keywords": ["hpc", "high performance computing", "mpi", "rdma", "slurm",
                           "cfd", "fea", "genomics", "scientific computing", "cluster"],
        "terraform_module": "oracle-quickstart/oci-hpc",
        "architecture_url": "https://docs.oracle.com/en/solutions/hpc-cluster/",
        "diagram_mermaid": """
graph TB
    User --> Head[Head Node - Job Scheduler]
    Head --> CN1[Compute Node 1 BM RDMA]
    Head --> CN2[Compute Node 2 BM RDMA]
    Head --> CN3[Compute Node N BM RDMA]
    CN1 <-->|RDMA 100 Gbps| CN2
    CN2 <-->|RDMA 100 Gbps| CN3
    CN1 --> FS[File Storage /scratch]
    CN2 --> FS
    CN3 --> FS
    FS --> OS[Object Storage results]
""",
        "estimated_monthly_cost_usd": 5000,
        "tags": ["hpc", "bare-metal", "rdma", "mpi"],
    },
    # ── AI / ML ───────────────────────────────────────────────────────────────
    {
        "template_id":   "oci-ai-ml-platform",
        "name":          "OCI AI/ML Platform (GPU + GenAI)",
        "category":      "AI & ML",
        "description":   (
            "End-to-end AI/ML platform combining OCI Data Science, GPU compute, "
            "OCI Generative AI Service, and Oracle Database 23ai Vector Store. "
            "Covers model training, fine-tuning, RAG pipelines, and inference serving."
        ),
        "complexity":    "high",
        "oci_services":  ["OCI Data Science", "GPU Compute", "OCI Generative AI",
                          "Oracle Database 23ai", "OCI Object Storage", "OCI Vault"],
        "components":    [
            "OCI Data Science (Jupyter notebooks, model catalog, pipelines)",
            "BM.GPU4.8 (8×A100) for training",
            "BM.GPU.A10.4 (4×A10) for inference",
            "OCI Generative AI Service (Cohere Command R+ / LLaMA 3)",
            "Oracle Database 23ai (vector search for RAG)",
            "Object Storage (training data, model artifacts)",
            "OCI Container Registry (custom model containers)",
            "OCI Functions (model serving endpoints)",
            "Vault (API keys, model credentials)",
        ],
        "source_providers": ["AWS", "Azure", "GCP"],
        "match_keywords": ["ai", "ml", "machine learning", "deep learning", "gpu",
                           "llm", "generative ai", "rag", "vector", "embedding",
                           "sagemaker", "vertex ai", "azure ml"],
        "terraform_module": "oracle-quickstart/oci-data-science",
        "architecture_url": "https://docs.oracle.com/en/solutions/ai-ml-oci/",
        "diagram_mermaid": """
graph TB
    Data[Training Data] --> OS[Object Storage]
    OS --> DS[OCI Data Science]
    DS --> GPU[A100 GPU Cluster]
    GPU --> Models[Model Artifacts OS]
    Models --> Inf[Inference GPU A10]
    Inf --> API[REST Serving Endpoint]
    GenAI[OCI GenAI Service] --> RAG[RAG Pipeline]
    DB23ai[Oracle DB 23ai Vector] --> RAG
    RAG --> API
""",
        "estimated_monthly_cost_usd": 15000,
        "tags": ["ai", "ml", "gpu", "genai", "rag", "vector-search"],
    },
    # ── HYBRID CLOUD ──────────────────────────────────────────────────────────
    {
        "template_id":   "oci-hybrid-cloud",
        "name":          "OCI Hybrid Cloud with FastConnect & On-Prem",
        "category":      "Hybrid",
        "description":   (
            "Extends on-premises data centres to OCI using FastConnect (dedicated circuit) "
            "and VPN Connect (IPSec backup). Dynamic Routing Gateway (DRG v2) provides "
            "transitive routing between on-prem, multiple VCNs, and OCI services."
        ),
        "complexity":    "high",
        "oci_services":  ["FastConnect", "VPN Connect", "DRG v2", "VCN", "Service Gateway",
                          "Oracle GoldenGate", "OCI Exadata"],
        "components":    [
            "FastConnect 10 Gbps dedicated circuit (via partner/colocation)",
            "VPN Connect (IKEv2 IPSec) — backup path",
            "DRG v2 with VCN attachments + remote peering",
            "On-premises CPE (customer-managed router)",
            "VCN: Hub-and-spoke topology",
            "Service Gateway (access to OCI services without internet)",
            "Oracle GoldenGate (real-time DB replication on-prem→OCI)",
            "OCI Vault (centralized secrets)",
        ],
        "source_providers": ["On-Premises"],
        "match_keywords": ["hybrid", "on-premises", "on-prem", "data centre", "datacenter",
                           "vpn", "direct connect", "expressroute", "fastconnect",
                           "private connectivity", "colocation"],
        "terraform_module": "oracle-quickstart/oci-network-firewall",
        "architecture_url": "https://docs.oracle.com/en/solutions/oci-hybrid-dns/",
        "diagram_mermaid": """
graph LR
    DC[On-Premises DC] -->|FastConnect 10Gbps| FC[FastConnect Port]
    DC -->|VPN Backup| VPN[VPN Connect IPSec]
    FC --> DRG[DRG v2]
    VPN --> DRG
    DRG --> Hub[Hub VCN]
    Hub --> App[App Spoke VCN]
    Hub --> DB[DB Spoke VCN]
    Hub --> SG[Service Gateway]
    SG --> OCI_SVC[OCI Services]
""",
        "estimated_monthly_cost_usd": 1200,
        "tags": ["hybrid", "fastconnect", "vpn", "on-premises", "drg"],
    },
    # ── SECURITY ─────────────────────────────────────────────────────────────
    {
        "template_id":   "oci-security-hub",
        "name":          "OCI Security Hub (Zero Trust)",
        "category":      "Security",
        "description":   (
            "Comprehensive Zero Trust security architecture for OCI using "
            "Network Firewall, WAF, Cloud Guard, Security Zones, OCI Bastion, "
            "Vault, and Certificate Service."
        ),
        "complexity":    "high",
        "oci_services":  ["OCI Network Firewall", "WAF", "Cloud Guard", "Security Zones",
                          "Bastion", "Vault", "Certificates", "IAM"],
        "components":    [
            "OCI Network Firewall (stateful L7 with TLS inspection)",
            "Web Application Firewall (OWASP + bot protection)",
            "Cloud Guard (CIS v2 recipe, threat detection)",
            "Security Zones (enforced policies, immutable settings)",
            "OCI Bastion (zero-trust SSH/RDP, no public IPs)",
            "Vault (HSM or Virtual, BYOK support)",
            "Certificates Service (TLS lifecycle management)",
            "Identity Domains (MFA, adaptive auth, SAML/OIDC)",
            "Logging Analytics (SIEM ingestion)",
        ],
        "source_providers": ["AWS", "Azure", "GCP", "On-Premises"],
        "match_keywords": ["security", "zero trust", "firewall", "waf", "siem",
                           "compliance", "pci", "hipaa", "iso 27001", "soc2",
                           "bastion", "privileged access", "mfa"],
        "terraform_module": "oracle-quickstart/oci-network-firewall",
        "architecture_url": "https://docs.oracle.com/en/solutions/oci-network-firewall-terraform/",
        "diagram_mermaid": """
graph TB
    Internet --> WAF[Web Application Firewall]
    WAF --> FW[OCI Network Firewall]
    FW --> LB[Load Balancer]
    LB --> APP[Application Tier]
    APP --> DB[Database Tier]
    CG[Cloud Guard] -.->|Monitors| APP
    CG -.->|Monitors| DB
    Bastion[OCI Bastion] -.->|Secure Access| APP
    Vault[Vault HSM] -.->|Key Mgmt| APP
    Vault -.->|Key Mgmt| DB
    LogAnalytics[Logging Analytics SIEM] -.->|Ingests| WAF
    LogAnalytics -.->|Ingests| APP
""",
        "estimated_monthly_cost_usd": 500,
        "tags": ["security", "zero-trust", "firewall", "waf", "cloud-guard"],
    },
]

# Build keyword index for fast matching
_KEYWORD_INDEX: Dict[str, List[str]] = {}
for tmpl in TEMPLATES:
    for kw in tmpl.get("match_keywords", []):
        _KEYWORD_INDEX.setdefault(kw.lower(), []).append(tmpl["template_id"])


class RefArchServer:
    SERVER_NAME = "refarch"
    VERSION = "2.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0.0
        self._by_id: Dict[str, Dict] = {t["template_id"]: t for t in TEMPLATES}

    def _record(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    # ------------------------------------------------------------------
    def list_templates(self, category: Optional[str] = None) -> Dict[str, Any]:
        """List all (or filtered) OCI reference architecture templates."""
        t0 = time.time()
        templates = (
            TEMPLATES if not category
            else [t for t in TEMPLATES if t["category"].lower() == category.lower()]
        )
        # Return summary view (no heavy fields)
        summaries = [
            {
                "template_id": t["template_id"],
                "name": t["name"],
                "category": t["category"],
                "complexity": t["complexity"],
                "description": t["description"][:120] + "…",
                "oci_services": t["oci_services"],
                "estimated_monthly_cost_usd": t.get("estimated_monthly_cost_usd"),
                "tags": t.get("tags", []),
            }
            for t in templates
        ]
        self._record((time.time() - t0) * 1000)
        return {"templates": summaries, "total": len(summaries)}

    # ------------------------------------------------------------------
    def get_template(self, template_id: str) -> Dict[str, Any]:
        """Retrieve a full template by ID."""
        t0 = time.time()
        template = self._by_id.get(template_id)
        self._record((time.time() - t0) * 1000)
        return {"template": template, "found": template is not None}

    # ------------------------------------------------------------------
    def match_pattern(
        self,
        architecture_description: str,
        services: Optional[List[str]] = None,
        source_provider: Optional[str] = None,
        complexity_preference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find the best-matching OCI reference architecture.

        Scoring:
          - Keyword match from description (each hit: +0.15)
          - Service match (each hit: +0.20)
          - Source provider match: +0.10
          - Complexity preference match: +0.05
        """
        t0 = time.time()
        description_lower = architecture_description.lower()
        services = [s.lower() for s in (services or [])]
        provider = (source_provider or "").upper()

        scored = []
        for tmpl in TEMPLATES:
            score = 0.0

            # Keyword matching against description
            for kw in tmpl.get("match_keywords", []):
                if kw.lower() in description_lower:
                    score += 0.15

            # Service matching
            for comp in tmpl.get("oci_services", []):
                comp_lower = comp.lower()
                if any(s in comp_lower or comp_lower in s for s in services):
                    score += 0.20

            # Provider matching
            if provider in [p.upper() for p in tmpl.get("source_providers", [])]:
                score += 0.10

            # Complexity preference
            if complexity_preference and tmpl["complexity"] == complexity_preference:
                score += 0.05

            scored.append({
                "template_id": tmpl["template_id"],
                "name": tmpl["name"],
                "category": tmpl["category"],
                "complexity": tmpl["complexity"],
                "match_score": round(min(score, 1.0), 3),
                "oci_services": tmpl["oci_services"],
                "estimated_monthly_cost_usd": tmpl.get("estimated_monthly_cost_usd"),
                "terraform_module": tmpl.get("terraform_module"),
                "architecture_url": tmpl.get("architecture_url"),
                "description": tmpl["description"][:200],
                "components": tmpl["components"],
            })

        scored.sort(key=lambda x: x["match_score"], reverse=True)
        self._record((time.time() - t0) * 1000)
        return {
            "best_match": scored[0] if scored else None,
            "alternatives": scored[1:3],
            "all_scored": scored,
        }

    # ------------------------------------------------------------------
    def get_categories(self) -> Dict[str, Any]:
        """List available architecture categories."""
        from collections import Counter
        cats = Counter(t["category"] for t in TEMPLATES)
        return {"categories": dict(cats), "total_templates": len(TEMPLATES)}

    # ------------------------------------------------------------------
    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
            "status": "healthy",
            "template_count": len(TEMPLATES),
        }


refarch_server = RefArchServer()
