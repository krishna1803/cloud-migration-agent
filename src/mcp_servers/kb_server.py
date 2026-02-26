"""MCP Server 1: Knowledge Base (kb) - Structured Rules/Scenarios Engine.

Backed by structured YAML knowledge files (not a vector database).
Provides rules, scenarios, service mappings, and risk assessment.

Tools (9):
  query_rules              - Query migration rules by domain/category
  query_applicable_rules   - Get rules applicable to a specific migration context
  get_scenario             - Get a specific migration scenario by name
  find_scenarios           - Find scenarios matching source/target cloud and service
  get_mappings             - Get service-level mappings for a given domain
  calculate_risk           - Calculate risk score for a migration scenario
  get_common_data          - Get common migration patterns and recommendations
  get_rules_for_scenario   - Get all rules associated with a scenario
  get_rule_by_id           - Retrieve a specific rule by ID
"""
import time
import random
from typing import Any, Dict, List, Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Inline structured knowledge (production systems load from YAML files)
# ---------------------------------------------------------------------------

_RULES: List[Dict[str, Any]] = [
    # Compute rules
    {"id": "COMP-001", "domain": "compute", "category": "sizing", "title": "Right-size compute instances", "severity": "HIGH",
     "description": "Map source instance types to OCI shapes using OCPU/RAM ratios. Consider workload-specific shapes (E4.Flex for general, A1.Flex for ARM, GPU for AI/ML).",
     "recommendation": "Use sizing MCP tool to map source instance to OCI shape.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    {"id": "COMP-002", "domain": "compute", "category": "licensing", "title": "Evaluate BYOL vs OCI licensing", "severity": "MEDIUM",
     "description": "Check if existing software licenses can be brought to OCI (BYOL) vs purchasing OCI-bundled licenses.",
     "recommendation": "Evaluate Oracle License Mobility for Oracle software.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    {"id": "COMP-003", "domain": "compute", "category": "availability", "title": "Multi-AD deployment for HA", "severity": "HIGH",
     "description": "Deploy critical compute across multiple Availability Domains for fault tolerance.",
     "recommendation": "Use Instance Pools with AD placement configured.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    # Storage rules
    {"id": "STOR-001", "domain": "storage", "category": "object_storage", "title": "Migrate to OCI Object Storage", "severity": "LOW",
     "description": "S3/Blob/GCS data can be migrated to OCI Object Storage using rclone or Data Transfer Service.",
     "recommendation": "Use OCI Data Transfer Service for large datasets (>100TB).", "applicable_sources": ["AWS", "Azure", "GCP"]},
    {"id": "STOR-002", "domain": "storage", "category": "block_storage", "title": "Configure Block Volume performance", "severity": "MEDIUM",
     "description": "OCI Block Volumes use VPUs to scale IOPS. Choose appropriate VPU tier based on workload.",
     "recommendation": "Use Higher Performance (20 VPU) for databases, Balanced (10 VPU) for general.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    # Database rules
    {"id": "DB-001", "domain": "database", "category": "migration", "title": "Use OCI Database Migration Service", "severity": "HIGH",
     "description": "Oracle DMS supports homogeneous (Oracle→Oracle) and heterogeneous (MySQL→ADB, PostgreSQL→ADB) migrations.",
     "recommendation": "Run DMS with initial load + CDC for minimal downtime.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    {"id": "DB-002", "domain": "database", "category": "autonomous", "title": "Evaluate Autonomous Database", "severity": "MEDIUM",
     "description": "ADB provides self-managing, self-tuning, and self-securing capabilities reducing DBA overhead.",
     "recommendation": "Use ATP for OLTP workloads, ADW for analytics.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    {"id": "DB-003", "domain": "database", "category": "backup", "title": "Configure automated backups", "severity": "HIGH",
     "description": "Enable automated backups with 30-day retention for all production databases.",
     "recommendation": "Use OCI Database backup to Object Storage with cross-region replication.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    # Networking rules
    {"id": "NET-001", "domain": "networking", "category": "vcn_design", "title": "Follow OCI VCN best practices", "severity": "HIGH",
     "description": "Design VCN with separate public/private subnets, use NGW for private subnet internet access.",
     "recommendation": "Use /16 CIDR for VCN, /24 subnets for tiers.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    {"id": "NET-002", "domain": "networking", "category": "connectivity", "title": "Evaluate FastConnect vs VPN", "severity": "MEDIUM",
     "description": "FastConnect provides dedicated 1-100Gbps connectivity; VPN suitable for <1Gbps or intermittent use.",
     "recommendation": "Use FastConnect for production, VPN for dev/test.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    # Security rules
    {"id": "SEC-001", "domain": "security", "category": "iam", "title": "Implement least-privilege IAM", "severity": "HIGH",
     "description": "Create OCI compartments per environment/team, apply least-privilege IAM policies.",
     "recommendation": "Use predefined OCI policy templates and avoid * (allow all) policies.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    {"id": "SEC-002", "domain": "security", "category": "encryption", "title": "Enable encryption at rest and in transit", "severity": "HIGH",
     "description": "All OCI storage is encrypted by default. Use customer-managed keys (CMK) via OCI Vault for compliance.",
     "recommendation": "Enable CMK for databases and Object Storage buckets.", "applicable_sources": ["AWS", "Azure", "GCP", "On-Premises"]},
    # Containers rules
    {"id": "CONT-001", "domain": "containers", "category": "kubernetes", "title": "Migrate to OKE (Oracle Container Engine)", "severity": "MEDIUM",
     "description": "OKE is CNCF-conformant Kubernetes. Kubernetes manifests can be migrated directly with minor adjustments.",
     "recommendation": "Update storage class references and load balancer annotations for OCI.", "applicable_sources": ["AWS", "Azure", "GCP"]},
    {"id": "CONT-002", "domain": "containers", "category": "registry", "title": "Use OCI Container Registry", "severity": "LOW",
     "description": "Migrate container images to OCI Container Registry (OCIR) for low-latency pulls within OCI.",
     "recommendation": "Use skopeo or crane to copy images from source registry to OCIR.", "applicable_sources": ["AWS", "Azure", "GCP"]},
]

_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "aws-ec2-to-oci-compute": {
        "name": "aws-ec2-to-oci-compute",
        "title": "Migrate AWS EC2 to OCI Compute",
        "source_cloud": "AWS", "source_service": "EC2",
        "target_service": "OCI Compute",
        "complexity": "low", "estimated_effort_days": 3,
        "risk_level": "LOW",
        "steps": ["Export AMI", "Convert image format", "Import custom image to OCI", "Launch instance", "Configure networking"],
        "applicable_rules": ["COMP-001", "COMP-002", "NET-001"],
    },
    "aws-rds-to-adb": {
        "name": "aws-rds-to-adb",
        "title": "Migrate AWS RDS to Oracle Autonomous Database",
        "source_cloud": "AWS", "source_service": "RDS",
        "target_service": "Autonomous Database",
        "complexity": "medium", "estimated_effort_days": 10,
        "risk_level": "MEDIUM",
        "steps": ["Export schema", "Run DMS migration assessment", "Configure DMS job", "Run initial load + CDC", "Validate and cutover"],
        "applicable_rules": ["DB-001", "DB-002", "DB-003"],
    },
    "aws-eks-to-oke": {
        "name": "aws-eks-to-oke",
        "title": "Migrate AWS EKS to OKE",
        "source_cloud": "AWS", "source_service": "EKS",
        "target_service": "OKE",
        "complexity": "medium", "estimated_effort_days": 7,
        "risk_level": "MEDIUM",
        "steps": ["Export K8s manifests", "Update storage classes", "Update LB annotations", "Create OKE cluster", "Deploy workloads", "Validate"],
        "applicable_rules": ["CONT-001", "CONT-002", "NET-001"],
    },
    "aws-s3-to-object-storage": {
        "name": "aws-s3-to-object-storage",
        "title": "Migrate AWS S3 to OCI Object Storage",
        "source_cloud": "AWS", "source_service": "S3",
        "target_service": "Object Storage",
        "complexity": "low", "estimated_effort_days": 2,
        "risk_level": "LOW",
        "steps": ["Inventory S3 buckets", "Configure rclone", "Run sync", "Validate checksums", "Update application configs"],
        "applicable_rules": ["STOR-001"],
    },
    "azure-aks-to-oke": {
        "name": "azure-aks-to-oke",
        "title": "Migrate Azure AKS to OKE",
        "source_cloud": "Azure", "source_service": "AKS",
        "target_service": "OKE",
        "complexity": "medium", "estimated_effort_days": 7,
        "risk_level": "MEDIUM",
        "steps": ["Export K8s manifests", "Update storage classes", "Create OKE cluster", "Deploy workloads", "Validate"],
        "applicable_rules": ["CONT-001", "CONT-002", "NET-001"],
    },
    "gcp-gke-to-oke": {
        "name": "gcp-gke-to-oke",
        "title": "Migrate GCP GKE to OKE",
        "source_cloud": "GCP", "source_service": "GKE",
        "target_service": "OKE",
        "complexity": "medium", "estimated_effort_days": 7,
        "risk_level": "MEDIUM",
        "steps": ["Export K8s manifests", "Update storage classes", "Create OKE cluster", "Deploy workloads", "Validate"],
        "applicable_rules": ["CONT-001", "CONT-002", "NET-001"],
    },
}

_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "compute": {"AWS": {"EC2": "OCI Compute"}, "Azure": {"Virtual Machines": "OCI Compute"}, "GCP": {"Compute Engine": "OCI Compute"}},
    "storage": {"AWS": {"S3": "Object Storage"}, "Azure": {"Blob Storage": "Object Storage"}, "GCP": {"Cloud Storage": "Object Storage"}},
    "database": {"AWS": {"RDS": "ADB/MySQL/PostgreSQL", "DynamoDB": "NoSQL"}, "Azure": {"Azure SQL": "ADB", "Cosmos DB": "NoSQL"}, "GCP": {"Cloud SQL": "ADB/MySQL", "Spanner": "ADB"}},
    "networking": {"AWS": {"VPC": "VCN", "ELB": "Load Balancer"}, "Azure": {"VNet": "VCN", "Azure LB": "Load Balancer"}, "GCP": {"VPC": "VCN", "Cloud LB": "Load Balancer"}},
    "security": {"AWS": {"IAM": "OCI IAM", "KMS": "OCI Vault"}, "Azure": {"Azure AD": "OCI IAM", "Key Vault": "OCI Vault"}, "GCP": {"Cloud IAM": "OCI IAM", "Cloud KMS": "OCI Vault"}},
    "containers": {"AWS": {"EKS": "OKE", "ECR": "OCIR"}, "Azure": {"AKS": "OKE", "ACR": "OCIR"}, "GCP": {"GKE": "OKE", "Artifact Registry": "OCIR"}},
}

_RULE_INDEX: Dict[str, Dict] = {r["id"]: r for r in _RULES}

_RISK_FACTORS = {
    "data_volume_tb": {"low": 0, "medium": 10, "high": 100},
    "downtime_tolerance_hours": {"low": 0, "medium": 4, "high": 24},
    "service_complexity": {"low": 1, "medium": 3, "high": 6},
}


class KBServer:
    """Knowledge Base MCP Server - Structured Rules/Scenarios Engine."""
    SERVER_NAME = "kb"
    VERSION = "2.0.0"

    def __init__(self):
        self.collections = ["service_mappings", "best_practices", "architecture_patterns", "pricing_info", "compliance_standards"]
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0

    def _record_call(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    def query(self, query_text: str, collection: str = "all", top_k: int = 5, migration_context=None) -> Dict[str, Any]:
        start = time.time()
        results = [
            {"document_id": f"doc_{collection}_{i+1}", "content": f"Relevant content for {query_text!r} from {collection}.",
             "relevance_score": round(0.95 - (i * 0.1), 2), "source": f"{collection}/document_{i+1}.md",
             "metadata": {"collection": collection}}
            for i in range(min(top_k, 3))
        ]
        answer = f"Based on the Oracle Cloud migration knowledge base: {query_text} - OCI provides equivalent services."
        latency = (time.time() - start) * 1000
        self._record_call(latency)
        return {"answer": answer, "retrieved_documents": results, "collection": collection, "query": query_text, "latency_ms": round(latency, 2)}

    def search(self, query_text: str, collection: str = "all") -> Dict[str, Any]:
        results = [{"id": f"result_{i}", "title": f"Result {i} for {query_text!r}", "collection": collection, "score": round(0.9 - (i * 0.05), 2)} for i in range(5)]
        return {"results": results, "total": len(results)}

    def add_document(self, content: str, collection: str, metadata=None, source: str = "user") -> Dict[str, Any]:
        doc_id = f"doc_{int(time.time())}_{random.randint(1000, 9999)}"
        return {"document_id": doc_id, "collection": collection, "status": "indexed", "chunks_created": max(1, len(content) // 500)}

    def query_service_mapping(self, source_service: str, source_provider: str) -> Dict[str, Any]:
        mappings = {
            "EC2": {"oci_service": "Compute Instance", "confidence": 0.95},
            "S3": {"oci_service": "Object Storage", "confidence": 0.98},
            "RDS": {"oci_service": "MySQL HeatWave / Autonomous Database", "confidence": 0.90},
            "VPC": {"oci_service": "Virtual Cloud Network (VCN)", "confidence": 0.99},
            "LAMBDA": {"oci_service": "OCI Functions", "confidence": 0.92},
            "EKS": {"oci_service": "Oracle Container Engine for Kubernetes (OKE)", "confidence": 0.95},
            "IAM": {"oci_service": "Identity and Access Management (IAM)", "confidence": 0.97},
            "ELB": {"oci_service": "Load Balancer", "confidence": 0.95},
        }
        mapping = mappings.get(source_service.upper(), {"oci_service": f"OCI equivalent for {source_service}", "confidence": 0.70})
        return {"source_service": source_service, "source_provider": source_provider, "mapping": mapping}

    def query_best_practices(self, topic: str) -> Dict[str, Any]:
        return {"topic": topic, "practices": [{"practice": f"Best practice for {topic}", "priority": "high"}]}

    def query_architecture_patterns(self, pattern_type: str) -> Dict[str, Any]:
        return {"pattern_type": pattern_type, "patterns": [{"name": f"OCI {pattern_type} Pattern", "components": ["VCN", "Compute", "Load Balancer"]}]}

    def query_pricing_info(self, service_name: str, region: str = "us-ashburn-1") -> Dict[str, Any]:
        return {"service": service_name, "region": region, "pricing": {"note": "Contact Oracle for exact pricing"}}

    def query_compliance_standards(self, standard: str) -> Dict[str, Any]:
        return {"standard": standard, "oci_compliance": True, "certifications": ["SOC 2", "ISO 27001", "PCI DSS", "HIPAA"]}

    def list_collections(self) -> Dict[str, Any]:
        return {"collections": [{"name": c, "document_count": random.randint(50, 500)} for c in self.collections]}

    # ------------------------------------------------------------------
    # Spec v4.1.0 Tools — Structured Rules/Scenarios Engine
    # ------------------------------------------------------------------

    def query_rules(
        self,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        source_cloud: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query migration rules by domain and/or category.

        Args:
            domain: Filter by domain (compute/storage/database/networking/security/containers)
            category: Filter by category (e.g. 'sizing', 'migration', 'iam')
            severity: Filter by severity (HIGH/MEDIUM/LOW)
            source_cloud: Filter by applicable source cloud (AWS/Azure/GCP/On-Premises)
        """
        t0 = time.time()
        rules = _RULES
        if domain:
            rules = [r for r in rules if r["domain"] == domain.lower()]
        if category:
            rules = [r for r in rules if r["category"] == category.lower()]
        if severity:
            rules = [r for r in rules if r["severity"] == severity.upper()]
        if source_cloud:
            rules = [r for r in rules if source_cloud in r.get("applicable_sources", [])]
        latency = (time.time() - t0) * 1000
        self._record_call(latency)
        return {"rules": rules, "total": len(rules), "filters": {"domain": domain, "category": category, "severity": severity}, "latency_ms": round(latency, 2)}

    def query_applicable_rules(
        self,
        source_cloud: str,
        services: List[str],
        domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get rules applicable to a specific migration context.

        Args:
            source_cloud: Source cloud provider (AWS/Azure/GCP/On-Premises)
            services: List of services being migrated (e.g. ['EC2', 'RDS', 'S3'])
            domains: Optional list of domains to restrict results
        """
        t0 = time.time()
        rules = [r for r in _RULES if source_cloud in r.get("applicable_sources", [])]
        if domains:
            rules = [r for r in rules if r["domain"] in [d.lower() for d in domains]]
        # Prioritize HIGH severity
        rules.sort(key=lambda r: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(r["severity"], 3))
        latency = (time.time() - t0) * 1000
        self._record_call(latency)
        return {"applicable_rules": rules, "total": len(rules), "source_cloud": source_cloud, "services": services, "latency_ms": round(latency, 2)}

    def get_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Get a specific migration scenario by name.

        Args:
            scenario_name: Scenario key (e.g. 'aws-ec2-to-oci-compute', 'aws-rds-to-adb')
        """
        t0 = time.time()
        scenario = _SCENARIOS.get(scenario_name)
        latency = (time.time() - t0) * 1000
        self._record_call(latency, success=scenario is not None)
        if not scenario:
            return {"error": f"Scenario '{scenario_name}' not found", "available": list(_SCENARIOS.keys()), "latency_ms": round(latency, 2)}
        return {**scenario, "latency_ms": round(latency, 2)}

    def find_scenarios(
        self,
        source_cloud: Optional[str] = None,
        source_service: Optional[str] = None,
        target_service: Optional[str] = None,
        complexity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find scenarios matching source/target cloud and service.

        Args:
            source_cloud: Filter by source cloud (AWS/Azure/GCP)
            source_service: Filter by source service name (e.g. 'RDS', 'EKS')
            target_service: Filter by OCI target service (e.g. 'OKE', 'Autonomous Database')
            complexity: Filter by complexity (low/medium/high)
        """
        t0 = time.time()
        matches = list(_SCENARIOS.values())
        if source_cloud:
            matches = [s for s in matches if s.get("source_cloud", "").upper() == source_cloud.upper()]
        if source_service:
            matches = [s for s in matches if source_service.upper() in s.get("source_service", "").upper()]
        if target_service:
            matches = [s for s in matches if target_service.lower() in s.get("target_service", "").lower()]
        if complexity:
            matches = [s for s in matches if s.get("complexity") == complexity.lower()]
        latency = (time.time() - t0) * 1000
        self._record_call(latency)
        return {"scenarios": matches, "total": len(matches), "latency_ms": round(latency, 2)}

    def get_mappings(self, domain: str, source_cloud: Optional[str] = None) -> Dict[str, Any]:
        """Get service-level mappings for a given domain.

        Args:
            domain: Migration domain (compute/storage/database/networking/security/containers)
            source_cloud: Optional source cloud filter (AWS/Azure/GCP)
        """
        t0 = time.time()
        domain_mappings = _MAPPINGS.get(domain.lower())
        if not domain_mappings:
            latency = (time.time() - t0) * 1000
            self._record_call(latency, success=False)
            return {"error": f"Domain '{domain}' not found", "available_domains": list(_MAPPINGS.keys()), "latency_ms": round(latency, 2)}
        result = domain_mappings if not source_cloud else {source_cloud: domain_mappings.get(source_cloud, {})}
        latency = (time.time() - t0) * 1000
        self._record_call(latency)
        return {"domain": domain, "mappings": result, "latency_ms": round(latency, 2)}

    def calculate_risk(
        self,
        source_cloud: str,
        services: List[str],
        data_volume_tb: float = 0,
        downtime_tolerance_hours: float = 4,
        has_compliance_requirements: bool = False,
        is_production: bool = True,
    ) -> Dict[str, Any]:
        """Calculate risk score for a migration scenario.

        Args:
            source_cloud: Source cloud provider
            services: List of services being migrated
            data_volume_tb: Amount of data to migrate in TB
            downtime_tolerance_hours: Allowed downtime window in hours
            has_compliance_requirements: Whether compliance (PCI/HIPAA/SOC2) applies
            is_production: Whether this is a production workload
        """
        t0 = time.time()
        score = 0.0

        # Data volume risk
        if data_volume_tb > 100:
            score += 30
        elif data_volume_tb > 10:
            score += 15
        else:
            score += 5

        # Downtime tolerance risk
        if downtime_tolerance_hours == 0:
            score += 25
        elif downtime_tolerance_hours < 4:
            score += 15
        else:
            score += 5

        # Service complexity
        complex_services = {"RDS", "AURORA", "DMS", "EKS", "AKS", "GKE", "MSK", "KAFKA", "EMR"}
        complex_count = sum(1 for s in services if s.upper() in complex_services)
        score += complex_count * 10

        # Compliance
        if has_compliance_requirements:
            score += 15

        # Production workload
        if is_production:
            score += 10

        # Normalize to 0-100
        score = min(score, 100)
        risk_level = "HIGH" if score >= 60 else "MEDIUM" if score >= 30 else "LOW"

        mitigations = []
        if data_volume_tb > 10:
            mitigations.append("Use OCI Data Transfer Service for large dataset migration")
        if downtime_tolerance_hours == 0:
            mitigations.append("Implement CDC (Change Data Capture) for zero-downtime migration")
        if has_compliance_requirements:
            mitigations.append("Engage OCI compliance team for regulatory review")
        if complex_count > 0:
            mitigations.append("Conduct proof-of-concept for complex service migrations")

        latency = (time.time() - t0) * 1000
        self._record_call(latency)
        return {
            "risk_score": round(score, 1),
            "risk_level": risk_level,
            "risk_factors": {
                "data_volume": "HIGH" if data_volume_tb > 100 else "MEDIUM" if data_volume_tb > 10 else "LOW",
                "downtime": "HIGH" if downtime_tolerance_hours == 0 else "MEDIUM" if downtime_tolerance_hours < 4 else "LOW",
                "service_complexity": "HIGH" if complex_count > 2 else "MEDIUM" if complex_count > 0 else "LOW",
                "compliance": "HIGH" if has_compliance_requirements else "LOW",
                "environment": "HIGH" if is_production else "LOW",
            },
            "mitigations": mitigations,
            "source_cloud": source_cloud,
            "latency_ms": round(latency, 2),
        }

    def get_common_data(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """Get common migration patterns and recommendations.

        Args:
            topic: Optional topic filter (e.g. 'networking', 'cost', 'security')
        """
        t0 = time.time()
        common = {
            "migration_strategies": [
                {"name": "Lift and Shift (Rehost)", "effort": "LOW", "risk": "LOW", "savings": "10-20%"},
                {"name": "Replatform", "effort": "MEDIUM", "risk": "MEDIUM", "savings": "20-40%"},
                {"name": "Re-architect", "effort": "HIGH", "risk": "HIGH", "savings": "40-70%"},
            ],
            "oci_advantages": [
                "Lower compute costs vs AWS/Azure (up to 55% for compute)",
                "Free egress between OCI regions",
                "OKE control plane is free",
                "Autonomous Database self-managing capabilities",
                "Oracle BYOL license mobility",
            ],
            "common_pitfalls": [
                "Underestimating data transfer time and costs",
                "Not accounting for application dependency mapping",
                "Insufficient testing before cutover",
                "Missing IAM policy configuration",
                "Not enabling monitoring/alerting post-migration",
            ],
            "best_practices": [
                "Start with non-production workloads",
                "Use OCI Landing Zone as foundation",
                "Enable Cloud Guard from day one",
                "Configure automated backups before cutover",
                "Implement tagging strategy for cost tracking",
            ],
        }
        if topic:
            filtered = {k: v for k, v in common.items() if topic.lower() in k.lower()}
            common = filtered if filtered else common
        latency = (time.time() - t0) * 1000
        self._record_call(latency)
        return {"data": common, "topic": topic, "latency_ms": round(latency, 2)}

    def get_rules_for_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Get all rules associated with a specific migration scenario.

        Args:
            scenario_name: Scenario key (e.g. 'aws-rds-to-adb')
        """
        t0 = time.time()
        scenario = _SCENARIOS.get(scenario_name)
        if not scenario:
            latency = (time.time() - t0) * 1000
            self._record_call(latency, success=False)
            return {"error": f"Scenario '{scenario_name}' not found", "available": list(_SCENARIOS.keys()), "latency_ms": round(latency, 2)}
        rule_ids = scenario.get("applicable_rules", [])
        rules = [_RULE_INDEX[rid] for rid in rule_ids if rid in _RULE_INDEX]
        latency = (time.time() - t0) * 1000
        self._record_call(latency)
        return {"scenario_name": scenario_name, "rules": rules, "total": len(rules), "latency_ms": round(latency, 2)}

    def get_rule_by_id(self, rule_id: str) -> Dict[str, Any]:
        """Retrieve a specific migration rule by its ID.

        Args:
            rule_id: Rule identifier (e.g. 'COMP-001', 'DB-002', 'NET-001')
        """
        t0 = time.time()
        rule = _RULE_INDEX.get(rule_id.upper())
        latency = (time.time() - t0) * 1000
        self._record_call(latency, success=rule is not None)
        if not rule:
            return {"error": f"Rule '{rule_id}' not found", "available_ids": list(_RULE_INDEX.keys()), "latency_ms": round(latency, 2)}
        return {**rule, "latency_ms": round(latency, 2)}

    def get_health_metrics(self) -> Dict[str, Any]:
        avg_latency = self._total_latency_ms / max(self._call_count, 1)
        success_rate = self._success_count / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "total_calls": self._call_count,
            "success_rate": success_rate,
            "avg_latency_ms": round(avg_latency, 2),
            "status": "healthy",
            "total_rules": len(_RULES),
            "total_scenarios": len(_SCENARIOS),
            "domains": list(_MAPPINGS.keys()),
        }


kb_server = KBServer()
