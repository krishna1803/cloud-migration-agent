"""MCP Server 7: Cost Estimation (pricing)."""
import time
from typing import Any, Dict, List, Optional


class PricingServer:
    SERVER_NAME = "pricing"
    VERSION = "1.0.0"

    OCI_COMPUTE_PRICING = {
        "VM.Standard.E4.Flex": {"per_ocpu_hour": 0.025,  "per_gb_ram_hour": 0.0015},
        "VM.Standard.A1.Flex": {"per_ocpu_hour": 0.01,   "per_gb_ram_hour": 0.0015},
    }
    OCI_STORAGE_PRICING = {
        "Object Storage Standard": 0.0255,
        "Block Volume":            0.0425,
        "File Storage":            0.08,
        "Archive Storage":         0.0026,
    }

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0

    def _record_call(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success: self._success_count += 1
        self._total_latency_ms += latency_ms

    def oci_estimate(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        start = time.time()
        line_items = []
        total_monthly = 0.0
        for resource in resources:
            rtype = resource.get("type", "")
            qty = resource.get("quantity", 1)
            if rtype == "compute":
                shape = resource.get("shape", "VM.Standard.E4.Flex")
                p = self.OCI_COMPUTE_PRICING.get(shape, {"per_ocpu_hour": 0.025, "per_gb_ram_hour": 0.0015})
                cost = qty * (resource.get("ocpu", 2) * p["per_ocpu_hour"] + resource.get("memory_gb", 16) * p["per_gb_ram_hour"]) * 730
            elif rtype == "storage":
                rate = self.OCI_STORAGE_PRICING.get(resource.get("storage_class", "Object Storage Standard"), 0.0255)
                cost = qty * resource.get("size_gb", 100) * rate
            elif rtype == "load_balancer":
                cost = qty * 0.025 * 730
            else:
                cost = resource.get("estimated_monthly_cost", 0)
            total_monthly += cost
            line_items.append({"resource": resource.get("name", rtype), "type": rtype, "quantity": qty, "monthly_cost_usd": round(cost, 2)})
        self._record_call((time.time() - start) * 1000)
        return {"line_items": line_items, "total_monthly_cost_usd": round(total_monthly, 2), "total_annual_cost_usd": round(total_monthly * 12, 2), "currency": "USD"}

    def compare_with_source(self, source_monthly_cost: float, oci_monthly_cost: float) -> Dict[str, Any]:
        savings = source_monthly_cost - oci_monthly_cost
        return {"source_monthly_cost_usd": source_monthly_cost, "oci_monthly_cost_usd": oci_monthly_cost, "monthly_savings_usd": round(savings, 2), "annual_savings_usd": round(savings * 12, 2), "savings_percentage": round(savings / max(source_monthly_cost, 1) * 100, 1)}

    def get_health_metrics(self) -> Dict[str, Any]:
        return {"server": self.SERVER_NAME, "total_calls": self._call_count, "success_rate": self._success_count / max(self._call_count, 1), "avg_latency_ms": 0, "status": "healthy"}


pricing_server = PricingServer()
