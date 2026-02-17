"""MCP Server 6: Resource Sizing (sizing)."""
import time
from typing import Any, Dict, List, Optional

AWS_SIZING = {
    "t3.micro":   {"ocpu": 1, "memory_gb": 1},  "t3.small":   {"ocpu": 1, "memory_gb": 2},
    "t3.medium":  {"ocpu": 1, "memory_gb": 4},  "t3.large":   {"ocpu": 1, "memory_gb": 8},
    "m5.large":   {"ocpu": 1, "memory_gb": 8},  "m5.xlarge":  {"ocpu": 2, "memory_gb": 16},
    "m5.2xlarge": {"ocpu": 4, "memory_gb": 32}, "c5.xlarge":  {"ocpu": 2, "memory_gb": 8},
    "c5.2xlarge": {"ocpu": 4, "memory_gb": 16}, "r5.large":   {"ocpu": 1, "memory_gb": 16},
    "r5.xlarge":  {"ocpu": 2, "memory_gb": 32},
}


class SizingServer:
    SERVER_NAME = "sizing"
    VERSION = "1.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0

    def _record_call(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success: self._success_count += 1
        self._total_latency_ms += latency_ms

    def estimate_compute(self, source_instance_type: str, source_provider: str = "AWS", workload_type: str = "general") -> Dict[str, Any]:
        start = time.time()
        sizing = AWS_SIZING.get(source_instance_type.lower(), {"ocpu": 2, "memory_gb": 16})
        monthly_cost = (sizing["ocpu"] * 0.025 + sizing["memory_gb"] * 0.0015) * 730
        self._record_call((time.time() - start) * 1000)
        return {"source_instance": source_instance_type, "recommended_shape": "VM.Standard.E4.Flex", "ocpu": sizing["ocpu"], "memory_gb": sizing["memory_gb"], "estimated_monthly_cost_usd": round(monthly_cost, 2), "confidence": 0.90}

    def estimate_storage(self, storage_type: str, size_gb: float, iops=None) -> Dict[str, Any]:
        start = time.time()
        pricing = {"s3": 0.0255, "object": 0.0255, "ebs": 0.0425, "block": 0.0425, "efs": 0.08, "file": 0.08}
        rate = pricing.get(storage_type.lower(), 0.0255)
        oci_service = "Object Storage" if storage_type.lower() in ["s3", "object"] else "Block Volume" if storage_type.lower() in ["ebs", "block"] else "File Storage"
        self._record_call((time.time() - start) * 1000)
        return {"source_storage_type": storage_type, "size_gb": size_gb, "oci_service": oci_service, "estimated_monthly_cost_usd": round(size_gb * rate, 2), "confidence": 0.92}

    def estimate_network(self, monthly_data_transfer_gb: float, num_load_balancers: int = 0) -> Dict[str, Any]:
        start = time.time()
        total = monthly_data_transfer_gb * 0.0085 + num_load_balancers * 18.25
        self._record_call((time.time() - start) * 1000)
        return {"monthly_data_transfer_gb": monthly_data_transfer_gb, "total_monthly_cost_usd": round(total, 2), "confidence": 0.85}

    def get_health_metrics(self) -> Dict[str, Any]:
        return {"server": self.SERVER_NAME, "total_calls": self._call_count, "success_rate": self._success_count / max(self._call_count, 1), "avg_latency_ms": 0, "status": "healthy"}


sizing_server = SizingServer()
