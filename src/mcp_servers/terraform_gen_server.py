"""MCP Server 9: Terraform Code Generation (terraform_gen)."""
import time
from typing import Any, Dict, List, Optional

PROVIDER_TF = 'terraform {\n  required_version = ">= 1.0.0"\n  required_providers {\n    oci = {\n      source  = "oracle/oci"\n      version = ">= 5.0.0"\n    }\n  }\n}\n\nprovider "oci" {\n  region = var.region\n}\n'


class TerraformGenServer:
    SERVER_NAME = "terraform_gen"
    VERSION = "1.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0

    def _record_call(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success: self._success_count += 1
        self._total_latency_ms += latency_ms

    def generate_provider(self, region: str = "us-ashburn-1") -> Dict[str, Any]:
        start = time.time()
        self._record_call((time.time() - start) * 1000)
        return {"file_name": "provider.tf", "content": PROVIDER_TF, "language": "hcl"}

    def generate_variables(self, variables: List[Dict[str, Any]]) -> Dict[str, Any]:
        start = time.time()
        default_vars = [
            {"name": "tenancy_ocid",    "type": "string", "description": "OCI Tenancy OCID"},
            {"name": "compartment_ocid","type": "string", "description": "Target compartment OCID"},
            {"name": "region",          "type": "string", "description": "OCI Region", "default": "us-ashburn-1"},
        ]
        all_vars = default_vars + (variables or [])
        lines = []
        for v in all_vars:
            lines.append(f'variable "{v["name"]}" {{\n  description = "{v.get("description", v["name"])}"\n  type        = {v.get("type", "string")}\n')
            if "default" in v:
                d = v["default"]
                lines.append(f'  default     = "{d}"\n' if isinstance(d, str) else f'  default     = {d}\n')
            lines.append("}\n")
        self._record_call((time.time() - start) * 1000)
        return {"file_name": "variables.tf", "content": "\n".join(lines), "variable_count": len(all_vars)}

    def generate_resource(self, resource_type: str, resource_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        display = config.get("name", resource_name)
        content = (f'resource "{resource_type}" "{resource_name}" {{\n'
                   f'  compartment_id = var.compartment_ocid\n'
                   f'  display_name   = "{display}"\n'
                   f'}}')
        self._record_call((time.time() - start) * 1000)
        return {"resource_type": resource_type, "resource_name": resource_name, "content": content}

    def generate_module(self, module_name: str, source: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        parts = [f'module "{module_name}" {{\n  source = "{source}"\n']
        for k, v in variables.items():
            if isinstance(v, str) and not v.startswith("var."):
                parts.append(f'  {k} = "{v}"\n')
            else:
                parts.append(f'  {k} = {v}\n')
        parts.append("}")
        self._record_call((time.time() - start) * 1000)
        return {"module_name": module_name, "content": "".join(parts)}

    def get_health_metrics(self) -> Dict[str, Any]:
        return {"server": self.SERVER_NAME, "total_calls": self._call_count, "success_rate": self._success_count / max(self._call_count, 1), "avg_latency_ms": 0, "status": "healthy"}


terraform_gen_server = TerraformGenServer()
