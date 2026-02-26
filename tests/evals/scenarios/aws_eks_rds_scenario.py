"""
Eval Scenario: AWS EKS + RDS Migration to OCI.

Covers: EKS, RDS Aurora, ElastiCache, ALB, S3, CloudWatch
Expected OCI targets: OKE, Autonomous DB, OCI Cache, Load Balancer, Object Storage, Monitoring
"""

from typing import Any, Dict, List

SCENARIO_ID = "aws_eks_rds"
SCENARIO_VERSION = "1.0.0"

INPUT = {
    "source_provider": "AWS",
    "user_context": (
        "We run a containerised microservices application on EKS with RDS Aurora PostgreSQL, "
        "ElastiCache Redis, an ALB in front, S3 for asset storage, and CloudWatch for monitoring. "
        "We need hipaa and pci_dss compliance."
    ),
    "uploaded_documents": [],
    "bom_file": None,
    "target_region": "us-ashburn-1",
}

# 6 source services with their expected OCI mappings
EXPECTED_SERVICES = [
    {"source": "EKS", "oci_target": "OKE", "resource_type": "container"},
    {"source": "RDS Aurora", "oci_target": "Autonomous Database", "resource_type": "database"},
    {"source": "ElastiCache", "oci_target": "OCI Cache with Redis", "resource_type": "cache"},
    {"source": "ALB", "oci_target": "OCI Load Balancer", "resource_type": "load_balancer"},
    {"source": "S3", "oci_target": "Object Storage", "resource_type": "storage"},
    {"source": "CloudWatch", "oci_target": "OCI Monitoring", "resource_type": "monitoring"},
]

EXPECTED_COMPLIANCE_FRAMEWORKS = {"hipaa", "pci_dss"}

EXPECTED_MIN_DEPLOYMENT_WAVES = 2

INVARIANTS: List[Dict[str, Any]] = [
    # Discovery invariants
    {
        "id": "eks_rds_001",
        "description": "At least 4 services discovered",
        "phase": "discovery",
        "field": "discovery.discovered_services",
        "check": "len(value) >= 4",
    },
    {
        "id": "eks_rds_002",
        "description": "Discovery confidence >= 0.6",
        "phase": "discovery",
        "field": "discovery.discovery_confidence",
        "check": "value >= 0.6",
    },
    # Security posture invariants
    {
        "id": "eks_rds_003",
        "description": "HIPAA compliance framework detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'hipaa' in value",
    },
    {
        "id": "eks_rds_004",
        "description": "PCI-DSS compliance framework detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'pci_dss' in value",
    },
    # Analysis invariants
    {
        "id": "eks_rds_005",
        "description": "At least 4 service mappings produced",
        "phase": "analysis",
        "field": "analysis.service_mappings",
        "check": "len(value) >= 4",
    },
    {
        "id": "eks_rds_006",
        "description": "Monthly cost estimate is positive",
        "phase": "analysis",
        "field": "analysis.total_monthly_cost_usd",
        "check": "value > 0",
    },
    # Dependency invariants
    {
        "id": "eks_rds_007",
        "description": "Deployment wave plan populated",
        "phase": "dependency",
        "field": "dependency_analysis",
        "check": "bool(value)",
    },
    # Implementation invariants
    {
        "id": "eks_rds_008",
        "description": "Terraform code generated",
        "phase": "implementation",
        "field": "implementation.generated_code",
        "check": "len(value) > 0",
    },
    # Deployment invariants
    {
        "id": "eks_rds_009",
        "description": "Deliverables package populated",
        "phase": "deployment",
        "field": "deliverables_package",
        "check": "bool(value)",
    },
    {
        "id": "eks_rds_010",
        "description": "Data lineage report captured",
        "phase": "deployment",
        "field": "data_lineage_report",
        "check": "bool(value) and value.get('total_fields', 0) > 0",
    },
]
