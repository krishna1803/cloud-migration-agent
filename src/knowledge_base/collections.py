"""Knowledge Base collection definitions for Oracle 23ai Vector DB."""

COLLECTIONS = {
    "service_mappings":     {"name": "service_mappings",     "description": "AWS/Azure/GCP to OCI service mappings",  "table_name": "KB_SERVICE_MAPPINGS"},
    "best_practices":       {"name": "best_practices",       "description": "Cloud migration best practices",         "table_name": "KB_BEST_PRACTICES"},
    "architecture_patterns":{"name": "architecture_patterns","description": "OCI reference architectures",            "table_name": "KB_ARCH_PATTERNS"},
    "pricing_info":         {"name": "pricing_info",         "description": "OCI pricing information",                "table_name": "KB_PRICING_INFO"},
    "compliance_standards": {"name": "compliance_standards", "description": "Security compliance standards",          "table_name": "KB_COMPLIANCE"},
}
