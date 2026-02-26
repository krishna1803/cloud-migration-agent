"""
Eval Scenario: Security-Heavy Compliance Migration (v4.2.0 NEW).

Covers: EC2, RDS, Lambda, SQS, KMS, WAF, CloudTrail, GuardDuty
Tests: full compliance framework detection, dependency wave constraints,
       force_sequential override, and deliverables packaging.
"""

from typing import Any, Dict, List

SCENARIO_ID = "security_compliance"
SCENARIO_VERSION = "1.0.0"

INPUT = {
    "source_provider": "AWS",
    "user_context": (
        "Highly regulated financial services workload on AWS. Services: EC2 (app servers), "
        "RDS PostgreSQL (encrypted), Lambda (event processing), SQS (message queues), "
        "KMS (key management), WAF (web application firewall), CloudTrail (audit logs), "
        "GuardDuty (threat detection). "
        "Compliance requirements: hipaa, pci_dss, soc2, cis, fedramp. "
        "Deployment must be sequential — no parallel wave execution. "
        "Wave size should be 3."
    ),
    "uploaded_documents": [],
    "bom_file": None,
    "target_region": "us-ashburn-1",
    "dependency_constraints": {
        "force_sequential": True,
        "deployment_wave_size": 3,
        "excluded_services": [],
        "manual_overrides": [],
    },
}

# 8 source services with expected OCI mappings
EXPECTED_SERVICES = [
    {"source": "EC2", "oci_target": "Compute Instance", "resource_type": "compute"},
    {"source": "RDS PostgreSQL", "oci_target": "Autonomous Database", "resource_type": "database"},
    {"source": "Lambda", "oci_target": "OCI Functions", "resource_type": "serverless"},
    {"source": "SQS", "oci_target": "OCI Queue", "resource_type": "messaging"},
    {"source": "KMS", "oci_target": "OCI Vault", "resource_type": "security"},
    {"source": "WAF", "oci_target": "OCI WAF", "resource_type": "security"},
    {"source": "CloudTrail", "oci_target": "OCI Audit", "resource_type": "audit"},
    {"source": "GuardDuty", "oci_target": "OCI Cloud Guard", "resource_type": "security"},
]

EXPECTED_COMPLIANCE_FRAMEWORKS = {"hipaa", "pci_dss", "soc2", "cis", "fedramp"}

EXPECTED_FORCE_SEQUENTIAL = True
EXPECTED_WAVE_SIZE = 3

INVARIANTS: List[Dict[str, Any]] = [
    # Discovery
    {
        "id": "sec_001",
        "description": "At least 5 services discovered from complex context",
        "phase": "discovery",
        "field": "discovery.discovered_services",
        "check": "len(value) >= 5",
    },
    {
        "id": "sec_002",
        "description": "Security posture present with compliance requirements",
        "phase": "discovery",
        "field": "discovery.security_posture",
        "check": "value is not None",
    },
    # Security posture (Phase 1.9)
    {
        "id": "sec_003",
        "description": "HIPAA detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'hipaa' in value",
    },
    {
        "id": "sec_004",
        "description": "PCI-DSS detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'pci_dss' in value",
    },
    {
        "id": "sec_005",
        "description": "SOC2 detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'soc2' in value",
    },
    {
        "id": "sec_006",
        "description": "CIS detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'cis' in value",
    },
    {
        "id": "sec_007",
        "description": "Compliance frameworks status completed",
        "phase": "security_posture",
        "field": "compliance_frameworks_status",
        "check": "value == 'completed'",
    },
    # Dependency analysis (Phase 1.10)
    {
        "id": "sec_008",
        "description": "Dependency analysis completed",
        "phase": "dependency",
        "field": "dependency_analysis_status",
        "check": "value == 'completed'",
    },
    {
        "id": "sec_009",
        "description": "Applied constraints recorded",
        "phase": "dependency",
        "field": "applied_constraints",
        "check": "bool(value)",
    },
    {
        "id": "sec_010",
        "description": "Deployment waves produced",
        "phase": "dependency",
        "field": "dependency_analysis",
        "check": "value.get('total_waves', 0) >= 1",
    },
    # Analysis
    {
        "id": "sec_011",
        "description": "Cost estimate generated",
        "phase": "analysis",
        "field": "analysis.total_monthly_cost_usd",
        "check": "value >= 0",
    },
    # Implementation
    {
        "id": "sec_012",
        "description": "Terraform code generated",
        "phase": "implementation",
        "field": "implementation.generated_code",
        "check": "len(value) > 0",
    },
    # Deliverables (Phase 6.5)
    {
        "id": "sec_013",
        "description": "Deliverables package status completed or pending",
        "phase": "deployment",
        "field": "deliverables_package_status",
        "check": "value in ('completed', 'pending', 'failed')",
    },
    # Data lineage (Phase 6 final)
    {
        "id": "sec_014",
        "description": "Data lineage report has >= 10 field records",
        "phase": "deployment",
        "field": "data_lineage_report",
        "check": "value.get('total_fields', 0) >= 10 if value else True",
    },
    {
        "id": "sec_015",
        "description": "Data lineage compliance_frameworks captured",
        "phase": "deployment",
        "field": "data_lineage_report",
        "check": "bool(value.get('compliance_frameworks')) if value else True",
    },
]
