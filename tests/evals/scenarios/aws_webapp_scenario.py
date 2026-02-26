"""
Eval Scenario: AWS 3-Tier Web Application Migration to OCI.

Covers: EC2, RDS MySQL, ALB, S3, CloudFront
Expected OCI targets: Compute Instance, MySQL DB System, Load Balancer, Object Storage, CDN
"""

from typing import Any, Dict, List

SCENARIO_ID = "aws_webapp"
SCENARIO_VERSION = "1.0.0"

INPUT = {
    "source_provider": "AWS",
    "user_context": (
        "We have a classic 3-tier web application: EC2 instances (web + app tier), "
        "RDS MySQL for the database, ALB for load balancing, S3 for static assets, "
        "and CloudFront as CDN. We need soc2 compliance."
    ),
    "uploaded_documents": [],
    "bom_file": None,
    "target_region": "eu-frankfurt-1",
}

# 5 source services with their expected OCI mappings
EXPECTED_SERVICES = [
    {"source": "EC2", "oci_target": "Compute Instance", "resource_type": "compute"},
    {"source": "RDS MySQL", "oci_target": "MySQL DB System", "resource_type": "database"},
    {"source": "ALB", "oci_target": "OCI Load Balancer", "resource_type": "load_balancer"},
    {"source": "S3", "oci_target": "Object Storage", "resource_type": "storage"},
    {"source": "CloudFront", "oci_target": "OCI CDN", "resource_type": "cdn"},
]

EXPECTED_COMPLIANCE_FRAMEWORKS = {"soc2"}

EXPECTED_MIN_DEPLOYMENT_WAVES = 2

INVARIANTS: List[Dict[str, Any]] = [
    {
        "id": "webapp_001",
        "description": "At least 3 services discovered",
        "phase": "discovery",
        "field": "discovery.discovered_services",
        "check": "len(value) >= 3",
    },
    {
        "id": "webapp_002",
        "description": "Discovery confidence >= 0.5",
        "phase": "discovery",
        "field": "discovery.discovery_confidence",
        "check": "value >= 0.5",
    },
    {
        "id": "webapp_003",
        "description": "SOC2 compliance framework detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'soc2' in value",
    },
    {
        "id": "webapp_004",
        "description": "At least 3 service mappings produced",
        "phase": "analysis",
        "field": "analysis.service_mappings",
        "check": "len(value) >= 3",
    },
    {
        "id": "webapp_005",
        "description": "Monthly cost estimate positive",
        "phase": "analysis",
        "field": "analysis.total_monthly_cost_usd",
        "check": "value > 0",
    },
    {
        "id": "webapp_006",
        "description": "Terraform code generated",
        "phase": "implementation",
        "field": "implementation.generated_code",
        "check": "len(value) > 0",
    },
    {
        "id": "webapp_007",
        "description": "Architecture components defined",
        "phase": "design",
        "field": "design.architecture_components",
        "check": "len(value) > 0",
    },
    {
        "id": "webapp_008",
        "description": "No critical errors in workflow",
        "phase": "all",
        "field": "errors",
        "check": "not any('critical' in e.lower() for e in value)",
    },
]
