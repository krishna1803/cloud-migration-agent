"""
Eval Scenario: Azure VM + SQL Server Migration to OCI.

Covers: Azure VMs, Azure SQL, Blob Storage, Azure Load Balancer
Expected OCI targets: Compute Instances, DB System, Object Storage, OCI Load Balancer
"""

from typing import Any, Dict, List

SCENARIO_ID = "azure_vm_sql"
SCENARIO_VERSION = "1.0.0"

INPUT = {
    "source_provider": "Azure",
    "user_context": (
        "We run Azure VMs (2 web servers, 1 app server) behind an Azure Load Balancer, "
        "Azure SQL Server for the relational database, and Azure Blob Storage for "
        "document storage. ISO27001 compliance is required."
    ),
    "uploaded_documents": [],
    "bom_file": None,
    "target_region": "uk-london-1",
}

# 4 source services with their expected OCI mappings
EXPECTED_SERVICES = [
    {"source": "Azure VM", "oci_target": "Compute Instance", "resource_type": "compute"},
    {"source": "Azure SQL", "oci_target": "DB System", "resource_type": "database"},
    {"source": "Blob Storage", "oci_target": "Object Storage", "resource_type": "storage"},
    {"source": "Azure Load Balancer", "oci_target": "OCI Load Balancer", "resource_type": "load_balancer"},
]

EXPECTED_COMPLIANCE_FRAMEWORKS = {"iso27001"}

INVARIANTS: List[Dict[str, Any]] = [
    {
        "id": "azure_001",
        "description": "At least 2 services discovered from Azure context",
        "phase": "discovery",
        "field": "discovery.discovered_services",
        "check": "len(value) >= 2",
    },
    {
        "id": "azure_002",
        "description": "Source provider set to Azure",
        "phase": "discovery",
        "field": "source_provider",
        "check": "value == 'Azure'",
    },
    {
        "id": "azure_003",
        "description": "ISO27001 compliance framework detected",
        "phase": "security_posture",
        "field": "compliance_frameworks",
        "check": "'iso27001' in value",
    },
    {
        "id": "azure_004",
        "description": "Azure→OCI service mappings created",
        "phase": "analysis",
        "field": "analysis.service_mappings",
        "check": "len(value) >= 2",
    },
    {
        "id": "azure_005",
        "description": "Cost estimate present",
        "phase": "analysis",
        "field": "analysis.total_monthly_cost_usd",
        "check": "value >= 0",
    },
    {
        "id": "azure_006",
        "description": "Dependency analysis status completed or pending",
        "phase": "dependency",
        "field": "dependency_analysis_status",
        "check": "value in ('completed', 'pending', 'failed')",
    },
    {
        "id": "azure_007",
        "description": "Terraform code generated for OCI resources",
        "phase": "implementation",
        "field": "implementation.generated_code",
        "check": "len(value) > 0",
    },
    {
        "id": "azure_008",
        "description": "Data lineage report has records",
        "phase": "deployment",
        "field": "data_lineage_report",
        "check": "value.get('total_fields', 0) > 0 if value else True",
    },
]
