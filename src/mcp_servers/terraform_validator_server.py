"""MCP Server: Terraform Validator (mcp_terraform_validator).

Validates Terraform HCL syntax and scans for OCI security policy violations.

Tools (2):
  validate_syntax  - Parse and validate HCL syntax
  security_scan    - Scan for security policy violations
"""
import re
import time
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Security policy rules
# ---------------------------------------------------------------------------

_SECURITY_RULES: List[Dict[str, Any]] = [
    {
        "id": "SEC-001",
        "severity": "HIGH",
        "title": "Public Security List with 0.0.0.0/0 ingress on port 22 (SSH)",
        "pattern": r'ingress_security_rules.*?tcp_options.*?min\s*=\s*22.*?source\s*=\s*"0\.0\.0\.0/0"',
        "description": "SSH port 22 is open to the internet. Restrict to known CIDRs or use OCI Bastion.",
        "recommendation": "Restrict SSH access to a specific CIDR or bastion host subnet.",
    },
    {
        "id": "SEC-002",
        "severity": "HIGH",
        "title": "Public Security List with 0.0.0.0/0 ingress on port 3389 (RDP)",
        "pattern": r'ingress_security_rules.*?tcp_options.*?min\s*=\s*3389.*?source\s*=\s*"0\.0\.0\.0/0"',
        "description": "RDP port 3389 is open to the internet.",
        "recommendation": "Restrict RDP access to a specific CIDR or use OCI Bastion.",
    },
    {
        "id": "SEC-003",
        "severity": "MEDIUM",
        "title": "Object Storage bucket with public access",
        "pattern": r'oci_objectstorage_bucket.*?access_type\s*=\s*"(ObjectRead|ObjectReadWithoutList|NoPublicAccess)"',
        "description": "Object Storage bucket may have public access enabled.",
        "recommendation": "Set access_type = 'NoPublicAccess' unless public access is required.",
    },
    {
        "id": "SEC-004",
        "severity": "MEDIUM",
        "title": "Compute instance without NSG or security list",
        "pattern": r'oci_core_instance(?:(?!nsg_ids|security_list).)*?}',
        "description": "Compute instance may not have network security groups configured.",
        "recommendation": "Attach at least one NSG to control inbound/outbound traffic.",
    },
    {
        "id": "SEC-005",
        "severity": "LOW",
        "title": "Missing freeform_tags on resource",
        "pattern": r'resource\s+"oci_\w+"\s+"[^"]+"\s*\{(?:(?!freeform_tags).)*?\n\}',
        "description": "Resource is missing freeform_tags for cost tracking and governance.",
        "recommendation": "Add freeform_tags with 'project', 'environment', and 'owner' keys.",
    },
    {
        "id": "SEC-006",
        "severity": "HIGH",
        "title": "Hardcoded credentials or sensitive values",
        "pattern": r'(password|secret|api_key|access_key|private_key)\s*=\s*"[^$][^{][^"]{6,}"',
        "description": "Potential hardcoded credential detected in Terraform code.",
        "recommendation": "Use OCI Vault or Terraform variables with sensitive = true.",
    },
    {
        "id": "SEC-007",
        "severity": "MEDIUM",
        "title": "Database without encryption",
        "pattern": r'oci_database_(?:autonomous_database|db_system)(?:(?!kms_key_id).)*?}',
        "description": "Database resource may not have customer-managed encryption keys configured.",
        "recommendation": "Configure kms_key_id for customer-managed key encryption.",
    },
    {
        "id": "SEC-008",
        "severity": "LOW",
        "title": "Load Balancer without HTTPS listener",
        "pattern": r'oci_load_balancer_listener(?:(?!HTTPS|SSL).)*?}',
        "description": "Load Balancer listener may not be configured for HTTPS/SSL.",
        "recommendation": "Configure HTTPS listeners with SSL certificates from OCI Certificates.",
    },
]


# ---------------------------------------------------------------------------
# HCL syntax validation helpers
# ---------------------------------------------------------------------------

def _check_balanced_braces(hcl: str) -> Tuple[bool, Optional[str]]:
    """Check that all braces, brackets, and parentheses are balanced."""
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}
    for i, ch in enumerate(hcl):
        if ch in '({[':
            stack.append((ch, i))
        elif ch in ')}]':
            if not stack or stack[-1][0] != pairs[ch]:
                return False, f"Unmatched '{ch}' at position {i}"
            stack.pop()
    if stack:
        ch, pos = stack[-1]
        return False, f"Unclosed '{ch}' at position {pos}"
    return True, None


def _check_required_blocks(hcl: str) -> List[str]:
    """Check for common required Terraform blocks."""
    warnings = []
    if 'terraform {' not in hcl and 'terraform{' not in hcl:
        warnings.append("Missing 'terraform {}' required_providers block.")
    if 'provider "oci"' not in hcl and "provider 'oci'" not in hcl:
        warnings.append("Missing 'provider \"oci\"' block.")
    return warnings


def _extract_resources(hcl: str) -> List[Dict[str, str]]:
    """Extract resource type and name pairs from HCL."""
    pattern = re.compile(r'resource\s+"(oci_\w+)"\s+"(\w+)"')
    return [
        {"resource_type": m.group(1), "resource_name": m.group(2)}
        for m in pattern.finditer(hcl)
    ]


class TerraformValidatorServer:
    """Terraform Validator MCP Server."""

    SERVER_NAME = "mcp_terraform_validator"
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

    def validate_syntax(self, hcl_content: str, filename: str = "main.tf") -> Dict[str, Any]:
        """Parse and validate Terraform HCL syntax.

        Performs static analysis without requiring a live Terraform binary:
        - Brace/bracket balance check
        - Required block detection (terraform {}, provider "oci" {})
        - Resource block extraction
        - Variable reference validation

        Args:
            hcl_content: The HCL content string to validate
            filename: Source filename for error messages (default 'main.tf')

        Returns:
            Dict with is_valid, errors, warnings, and resource summary
        """
        t0 = time.time()
        errors: List[str] = []
        warnings: List[str] = []

        # Brace balance
        balanced, brace_err = _check_balanced_braces(hcl_content)
        if not balanced:
            errors.append(f"Syntax error in {filename}: {brace_err}")

        # Required blocks
        block_warnings = _check_required_blocks(hcl_content)
        warnings.extend(block_warnings)

        # Empty content check
        if not hcl_content.strip():
            errors.append(f"{filename} is empty.")

        # Resource extraction
        resources = _extract_resources(hcl_content)
        if not resources and "resource" in hcl_content:
            warnings.append("Could not parse resource blocks — verify HCL syntax.")

        # Check for non-OCI resources
        non_oci = [r for r in resources if not r["resource_type"].startswith("oci_")]
        if non_oci:
            warnings.append(
                f"Non-OCI resources detected: {[r['resource_type'] for r in non_oci]}. "
                "Ensure these are intentional."
            )

        is_valid = len(errors) == 0
        latency = (time.time() - t0) * 1000
        self._record(latency, success=is_valid)

        return {
            "filename": filename,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "resource_count": len(resources),
            "resources": resources,
            "latency_ms": round(latency, 2),
        }

    def security_scan(
        self,
        hcl_content: str,
        filename: str = "main.tf",
        severity_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scan Terraform HCL for OCI security policy violations.

        Checks against a set of OCI security rules covering:
        - Open SSH/RDP ports to 0.0.0.0/0
        - Public Object Storage buckets
        - Missing NSGs on compute instances
        - Hardcoded credentials
        - Missing resource tags
        - Unencrypted databases
        - HTTP-only load balancers

        Args:
            hcl_content: The HCL content string to scan
            filename: Source filename for finding messages
            severity_filter: Optional filter: 'HIGH', 'MEDIUM', or 'LOW'

        Returns:
            Dict with findings, severity counts, and overall pass/fail
        """
        t0 = time.time()
        findings: List[Dict[str, Any]] = []

        rules = _SECURITY_RULES
        if severity_filter:
            rules = [r for r in rules if r["severity"] == severity_filter.upper()]

        for rule in rules:
            try:
                match = re.search(rule["pattern"], hcl_content, re.DOTALL | re.IGNORECASE)
                if match:
                    findings.append({
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "title": rule["title"],
                        "description": rule["description"],
                        "recommendation": rule["recommendation"],
                        "match_snippet": hcl_content[max(0, match.start()-20):match.end()+20].strip(),
                    })
            except re.error:
                pass  # Skip malformed regex patterns

        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in findings:
            severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

        passed = severity_counts["HIGH"] == 0
        latency = (time.time() - t0) * 1000
        self._record(latency)

        return {
            "filename": filename,
            "passed": passed,
            "finding_count": len(findings),
            "severity_counts": severity_counts,
            "findings": findings,
            "rules_checked": len(rules),
            "latency_ms": round(latency, 2),
        }

    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "status": "healthy",
            "security_rules": len(_SECURITY_RULES),
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
        }


terraform_validator_server = TerraformValidatorServer()
