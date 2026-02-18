"""MCP Server 6: OCI Resource Sizing.

Maps AWS / Azure / GCP instance types to the best-fit OCI compute shape
and provides right-sizing recommendations with cost comparisons.

OCI shapes reference: https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm
"""
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# OCI SHAPE CATALOGUE — VCPU & memory max, pricing, workload suitability
# ---------------------------------------------------------------------------
OCI_SHAPES: Dict[str, Dict] = {
    # ── Flex VMs ────────────────────────────────────────────────────────────
    "VM.Standard.E4.Flex": {
        "processor": "AMD EPYC Milan", "arch": "x86_64",
        "max_ocpu": 64, "max_gb_ram": 1024,
        "per_ocpu_hour": 0.025, "per_gb_ram_hour": 0.0015,
        "network_gbps": 40,
        "best_for": ["web", "app", "general", "microservices", "batch"],
        "description": "Best price-performance for general-purpose workloads",
    },
    "VM.Standard.E5.Flex": {
        "processor": "AMD EPYC Genoa", "arch": "x86_64",
        "max_ocpu": 94, "max_gb_ram": 1049,
        "per_ocpu_hour": 0.025, "per_gb_ram_hour": 0.0015,
        "network_gbps": 50,
        "best_for": ["web", "app", "general", "microservices"],
        "description": "Latest-gen AMD for improved single-thread performance",
    },
    "VM.Standard3.Flex": {
        "processor": "Intel Xeon Ice Lake", "arch": "x86_64",
        "max_ocpu": 32, "max_gb_ram": 512,
        "per_ocpu_hour": 0.025, "per_gb_ram_hour": 0.0015,
        "network_gbps": 32,
        "best_for": ["web", "app", "general"],
        "description": "Intel-based flex VM for mixed workloads",
    },
    "VM.Standard.A1.Flex": {
        "processor": "Ampere A1 (ARM64)", "arch": "aarch64",
        "max_ocpu": 80, "max_gb_ram": 512,
        "per_ocpu_hour": 0.01, "per_gb_ram_hour": 0.0015,
        "network_gbps": 32,
        "best_for": ["cloud-native", "containers", "microservices", "web", "devops"],
        "description": "Most cost-effective shape; ARM-native apps run ~40% cheaper",
    },
    "VM.Optimized3.Flex": {
        "processor": "Intel Xeon Ice Lake 3.0 GHz turbo", "arch": "x86_64",
        "max_ocpu": 18, "max_gb_ram": 256,
        "per_ocpu_hour": 0.0425, "per_gb_ram_hour": 0.0025,
        "network_gbps": 20,
        "best_for": ["hpc", "gaming", "compute-intensive", "simulation"],
        "description": "High clock-speed compute for latency-sensitive workloads",
    },
    # ── Dense I/O ────────────────────────────────────────────────────────────
    "VM.DenseIO.E4.Flex": {
        "processor": "AMD EPYC Milan", "arch": "x86_64",
        "max_ocpu": 32, "max_gb_ram": 512,
        "per_ocpu_hour": 0.06, "per_gb_ram_hour": 0.0015,
        "local_nvme_tb": 6.4,
        "network_gbps": 40,
        "best_for": ["olap", "database", "big-data", "io-intensive"],
        "description": "High-throughput local NVMe for OLAP and large DBs",
    },
    # ── Bare Metal ───────────────────────────────────────────────────────────
    "BM.Standard.E4.128": {
        "processor": "AMD EPYC Milan", "arch": "x86_64",
        "ocpu": 128, "gb_ram": 2048,
        "flat_rate_hour": 2.976,
        "network_gbps": 100, "local_nvme_tb": 6.8,
        "best_for": ["dedicated", "hpc", "database", "large-enterprise"],
        "description": "128-OCPU AMD bare metal — dedicated, no hypervisor overhead",
    },
    "BM.Standard.A1.160": {
        "processor": "Ampere A1 (ARM64)", "arch": "aarch64",
        "ocpu": 160, "gb_ram": 1024,
        "flat_rate_hour": 1.52,
        "network_gbps": 100,
        "best_for": ["cloud-native", "arm", "large-scale"],
        "description": "160-OCPU ARM64 bare metal — cost-efficient at scale",
    },
    # ── GPU ──────────────────────────────────────────────────────────────────
    "BM.GPU4.8": {
        "processor": "Intel Xeon + 8×A100 80GB", "arch": "x86_64",
        "ocpu": 64, "gb_ram": 2048, "gpu_count": 8,
        "flat_rate_hour": 32.0,
        "best_for": ["ai", "ml", "deep-learning", "training"],
        "description": "8×NVIDIA A100 for large model training",
    },
    "BM.GPU.A10.4": {
        "processor": "Intel Xeon + 4×A10 24GB", "arch": "x86_64",
        "ocpu": 64, "gb_ram": 1024, "gpu_count": 4,
        "flat_rate_hour": 4.0,
        "best_for": ["inference", "rendering", "ai-inference"],
        "description": "4×NVIDIA A10 for cost-effective AI inference",
    },
}

# ---------------------------------------------------------------------------
# WORKLOAD-TYPE → SHAPE RECOMMENDATIONS (ordered preference)
# ---------------------------------------------------------------------------
WORKLOAD_SHAPE_MATRIX: Dict[str, List[str]] = {
    "general":        ["VM.Standard.E4.Flex", "VM.Standard.E5.Flex", "VM.Standard3.Flex"],
    "web":            ["VM.Standard.E4.Flex", "VM.Standard.A1.Flex", "VM.Standard.E5.Flex"],
    "app":            ["VM.Standard.E4.Flex", "VM.Standard.E5.Flex", "VM.Standard3.Flex"],
    "microservices":  ["VM.Standard.A1.Flex", "VM.Standard.E4.Flex", "VM.Standard.E5.Flex"],
    "compute":        ["VM.Optimized3.Flex",  "VM.Standard.E4.Flex", "VM.Standard.E5.Flex"],
    "hpc":            ["VM.Optimized3.Flex",  "BM.Standard.E4.128"],
    "memory":         ["VM.Standard.E4.Flex", "BM.Standard.E4.128"],
    "database":       ["VM.DenseIO.E4.Flex",  "VM.Standard.E4.Flex", "BM.Standard.E4.128"],
    "io-intensive":   ["VM.DenseIO.E4.Flex",  "VM.Standard.E4.Flex"],
    "ai":             ["BM.GPU4.8",           "BM.GPU.A10.4"],
    "inference":      ["BM.GPU.A10.4",        "VM.Standard.A1.Flex"],
    "containers":     ["VM.Standard.A1.Flex", "VM.Standard.E4.Flex"],
    "arm":            ["VM.Standard.A1.Flex", "BM.Standard.A1.160"],
    "batch":          ["VM.Standard.E4.Flex", "VM.Standard.A1.Flex"],
    "analytics":      ["VM.DenseIO.E4.Flex",  "VM.Standard.E4.Flex"],
}

# ---------------------------------------------------------------------------
# AWS EC2 → OCI SHAPE MAPPING
# 1 AWS vCPU = 1 OCI OCPU (OCI OCPU = 2 hardware threads on AMD/Intel)
# ---------------------------------------------------------------------------
AWS_TO_OCI: Dict[str, Dict] = {
    # T-series (burstable)
    "t3.nano":     {"ocpu": 1, "memory_gb": 0.5,  "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "t3.micro":    {"ocpu": 1, "memory_gb": 1,    "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "t3.small":    {"ocpu": 1, "memory_gb": 2,    "shape": "VM.Standard.E4.Flex", "workload": "web"},
    "t3.medium":   {"ocpu": 1, "memory_gb": 4,    "shape": "VM.Standard.E4.Flex", "workload": "web"},
    "t3.large":    {"ocpu": 1, "memory_gb": 8,    "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "t3.xlarge":   {"ocpu": 2, "memory_gb": 16,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "t3.2xlarge":  {"ocpu": 4, "memory_gb": 32,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "t4g.small":   {"ocpu": 1, "memory_gb": 2,    "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "t4g.medium":  {"ocpu": 1, "memory_gb": 4,    "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "t4g.large":   {"ocpu": 1, "memory_gb": 8,    "shape": "VM.Standard.A1.Flex", "workload": "general"},
    # M-series (general purpose)
    "m5.large":    {"ocpu": 1, "memory_gb": 8,    "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "m5.xlarge":   {"ocpu": 2, "memory_gb": 16,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "m5.2xlarge":  {"ocpu": 4, "memory_gb": 32,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "m5.4xlarge":  {"ocpu": 8, "memory_gb": 64,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "m5.8xlarge":  {"ocpu": 16,"memory_gb": 128,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "m5.12xlarge": {"ocpu": 24,"memory_gb": 192,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "m5.16xlarge": {"ocpu": 32,"memory_gb": 256,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "m5.24xlarge": {"ocpu": 48,"memory_gb": 384,  "shape": "BM.Standard.E4.128",  "workload": "general"},
    "m6g.large":   {"ocpu": 1, "memory_gb": 8,    "shape": "VM.Standard.A1.Flex", "workload": "general"},
    "m6g.xlarge":  {"ocpu": 2, "memory_gb": 16,   "shape": "VM.Standard.A1.Flex", "workload": "general"},
    "m6g.2xlarge": {"ocpu": 4, "memory_gb": 32,   "shape": "VM.Standard.A1.Flex", "workload": "general"},
    "m6g.4xlarge": {"ocpu": 8, "memory_gb": 64,   "shape": "VM.Standard.A1.Flex", "workload": "general"},
    # C-series (compute optimized)
    "c5.large":    {"ocpu": 1, "memory_gb": 4,    "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c5.xlarge":   {"ocpu": 2, "memory_gb": 8,    "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c5.2xlarge":  {"ocpu": 4, "memory_gb": 16,   "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c5.4xlarge":  {"ocpu": 8, "memory_gb": 32,   "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c5.9xlarge":  {"ocpu": 18,"memory_gb": 72,   "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c6g.large":   {"ocpu": 1, "memory_gb": 4,    "shape": "VM.Standard.A1.Flex", "workload": "compute"},
    "c6g.xlarge":  {"ocpu": 2, "memory_gb": 8,    "shape": "VM.Standard.A1.Flex", "workload": "compute"},
    "c6g.2xlarge": {"ocpu": 4, "memory_gb": 16,   "shape": "VM.Standard.A1.Flex", "workload": "compute"},
    # R-series (memory optimized)
    "r5.large":    {"ocpu": 1, "memory_gb": 16,   "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "r5.xlarge":   {"ocpu": 2, "memory_gb": 32,   "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "r5.2xlarge":  {"ocpu": 4, "memory_gb": 64,   "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "r5.4xlarge":  {"ocpu": 8, "memory_gb": 128,  "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "r5.8xlarge":  {"ocpu": 16,"memory_gb": 256,  "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "r5.16xlarge": {"ocpu": 32,"memory_gb": 512,  "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    # I-series (storage optimized)
    "i3.large":    {"ocpu": 1, "memory_gb": 15.25,"shape": "VM.DenseIO.E4.Flex",  "workload": "io-intensive"},
    "i3.xlarge":   {"ocpu": 2, "memory_gb": 30.5, "shape": "VM.DenseIO.E4.Flex",  "workload": "io-intensive"},
    "i3.2xlarge":  {"ocpu": 4, "memory_gb": 61,   "shape": "VM.DenseIO.E4.Flex",  "workload": "io-intensive"},
    "i3.4xlarge":  {"ocpu": 8, "memory_gb": 122,  "shape": "VM.DenseIO.E4.Flex",  "workload": "io-intensive"},
    # P-series / G-series (GPU)
    "p3.2xlarge":  {"ocpu": 4, "memory_gb": 61,   "shape": "BM.GPU.A10.4",        "workload": "ai", "note": "1xV100 → A10 (equivalent inference performance)"},
    "p3.8xlarge":  {"ocpu": 16,"memory_gb": 244,  "shape": "BM.GPU4.8",           "workload": "ai", "note": "4xV100 → A100 (improved)"},
    "p4d.24xlarge":{"ocpu": 48,"memory_gb": 1152, "shape": "BM.GPU4.8",           "workload": "ai"},
    "g4dn.xlarge": {"ocpu": 2, "memory_gb": 16,   "shape": "BM.GPU.A10.4",        "workload": "inference"},
    "g4dn.2xlarge":{"ocpu": 4, "memory_gb": 32,   "shape": "BM.GPU.A10.4",        "workload": "inference"},
}

# ---------------------------------------------------------------------------
# AZURE VM → OCI SHAPE MAPPING
# ---------------------------------------------------------------------------
AZURE_TO_OCI: Dict[str, Dict] = {
    # B-series (burstable)
    "Standard_B1s":   {"ocpu": 1, "memory_gb": 1,   "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "Standard_B1ms":  {"ocpu": 1, "memory_gb": 2,   "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "Standard_B2s":   {"ocpu": 1, "memory_gb": 4,   "shape": "VM.Standard.E4.Flex", "workload": "web"},
    "Standard_B2ms":  {"ocpu": 1, "memory_gb": 8,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "Standard_B4ms":  {"ocpu": 2, "memory_gb": 16,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "Standard_B8ms":  {"ocpu": 4, "memory_gb": 32,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    # D-series (general purpose)
    "Standard_D2s_v3":{"ocpu": 1, "memory_gb": 8,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "Standard_D4s_v3":{"ocpu": 2, "memory_gb": 16,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "Standard_D8s_v3":{"ocpu": 4, "memory_gb": 32,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "Standard_D16s_v3":{"ocpu": 8,"memory_gb": 64,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "Standard_D32s_v3":{"ocpu": 16,"memory_gb": 128,"shape": "VM.Standard.E4.Flex", "workload": "general"},
    "Standard_D2s_v5":{"ocpu": 1, "memory_gb": 8,   "shape": "VM.Standard.E5.Flex", "workload": "general"},
    "Standard_D4s_v5":{"ocpu": 2, "memory_gb": 16,  "shape": "VM.Standard.E5.Flex", "workload": "general"},
    "Standard_D8s_v5":{"ocpu": 4, "memory_gb": 32,  "shape": "VM.Standard.E5.Flex", "workload": "general"},
    # F-series (compute optimized)
    "Standard_F2s_v2":{"ocpu": 1, "memory_gb": 4,   "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "Standard_F4s_v2":{"ocpu": 2, "memory_gb": 8,   "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "Standard_F8s_v2":{"ocpu": 4, "memory_gb": 16,  "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "Standard_F16s_v2":{"ocpu": 8,"memory_gb": 32,  "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    # E-series (memory optimized)
    "Standard_E2s_v3":{"ocpu": 1, "memory_gb": 16,  "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "Standard_E4s_v3":{"ocpu": 2, "memory_gb": 32,  "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "Standard_E8s_v3":{"ocpu": 4, "memory_gb": 64,  "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "Standard_E16s_v3":{"ocpu": 8,"memory_gb": 128, "shape": "VM.Standard.E4.Flex", "workload": "memory"},
    "Standard_E32s_v3":{"ocpu": 16,"memory_gb": 256,"shape": "VM.Standard.E4.Flex", "workload": "memory"},
    # L-series (storage optimized)
    "Standard_L4s":   {"ocpu": 2, "memory_gb": 32,  "shape": "VM.DenseIO.E4.Flex",  "workload": "io-intensive"},
    "Standard_L8s_v2":{"ocpu": 4, "memory_gb": 64,  "shape": "VM.DenseIO.E4.Flex",  "workload": "io-intensive"},
    "Standard_L16s_v2":{"ocpu": 8,"memory_gb": 128, "shape": "VM.DenseIO.E4.Flex",  "workload": "io-intensive"},
    # N-series (GPU)
    "Standard_NC6":   {"ocpu": 3, "memory_gb": 56,  "shape": "BM.GPU.A10.4",        "workload": "ai"},
    "Standard_NC12":  {"ocpu": 6, "memory_gb": 112, "shape": "BM.GPU.A10.4",        "workload": "ai"},
    "Standard_NC24":  {"ocpu": 12,"memory_gb": 224, "shape": "BM.GPU4.8",           "workload": "ai"},
    "Standard_ND40rs_v2":{"ocpu": 20,"memory_gb": 672,"shape": "BM.GPU4.8",         "workload": "ai"},
}

# ---------------------------------------------------------------------------
# GCP MACHINE TYPE → OCI SHAPE MAPPING
# ---------------------------------------------------------------------------
GCP_TO_OCI: Dict[str, Dict] = {
    # E2 (general purpose economy)
    "e2-micro":      {"ocpu": 1, "memory_gb": 1,   "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "e2-small":      {"ocpu": 1, "memory_gb": 2,   "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "e2-medium":     {"ocpu": 1, "memory_gb": 4,   "shape": "VM.Standard.A1.Flex", "workload": "web"},
    "e2-standard-2": {"ocpu": 1, "memory_gb": 8,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "e2-standard-4": {"ocpu": 2, "memory_gb": 16,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "e2-standard-8": {"ocpu": 4, "memory_gb": 32,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "e2-standard-16":{"ocpu": 8, "memory_gb": 64,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    # N2 (general purpose)
    "n2-standard-2": {"ocpu": 1, "memory_gb": 8,   "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "n2-standard-4": {"ocpu": 2, "memory_gb": 16,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "n2-standard-8": {"ocpu": 4, "memory_gb": 32,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "n2-standard-16":{"ocpu": 8, "memory_gb": 64,  "shape": "VM.Standard.E4.Flex", "workload": "general"},
    "n2-standard-32":{"ocpu": 16,"memory_gb": 128, "shape": "VM.Standard.E4.Flex", "workload": "general"},
    # C2 (compute optimized)
    "c2-standard-4": {"ocpu": 2, "memory_gb": 16,  "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c2-standard-8": {"ocpu": 4, "memory_gb": 32,  "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c2-standard-16":{"ocpu": 8, "memory_gb": 64,  "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    "c2-standard-30":{"ocpu": 15,"memory_gb": 120, "shape": "VM.Optimized3.Flex",  "workload": "compute"},
    # M1/M2 (memory optimized)
    "m1-megamem-96": {"ocpu": 48,"memory_gb": 1433,"shape": "BM.Standard.E4.128",  "workload": "memory"},
    "m2-megamem-416":{"ocpu": 208,"memory_gb": 5888,"shape": "BM.Standard.E4.128", "workload": "memory"},
    # T2A (ARM)
    "t2a-standard-1":{"ocpu": 1, "memory_gb": 4,   "shape": "VM.Standard.A1.Flex", "workload": "general"},
    "t2a-standard-2":{"ocpu": 2, "memory_gb": 8,   "shape": "VM.Standard.A1.Flex", "workload": "general"},
    "t2a-standard-4":{"ocpu": 4, "memory_gb": 16,  "shape": "VM.Standard.A1.Flex", "workload": "general"},
    "t2a-standard-8":{"ocpu": 8, "memory_gb": 32,  "shape": "VM.Standard.A1.Flex", "workload": "general"},
    # A2 (GPU)
    "a2-highgpu-1g": {"ocpu": 6, "memory_gb": 85,  "shape": "BM.GPU.A10.4",        "workload": "ai"},
    "a2-highgpu-2g": {"ocpu": 12,"memory_gb": 170, "shape": "BM.GPU.A10.4",        "workload": "ai"},
    "a2-highgpu-4g": {"ocpu": 24,"memory_gb": 340, "shape": "BM.GPU4.8",           "workload": "ai"},
    "a2-highgpu-8g": {"ocpu": 48,"memory_gb": 680, "shape": "BM.GPU4.8",           "workload": "ai"},
}

# ---------------------------------------------------------------------------
# AWS source pricing for comparison (simplified On-Demand, us-east-1)
# ---------------------------------------------------------------------------
AWS_PRICING: Dict[str, float] = {
    "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416,
    "t3.large": 0.0832, "t3.xlarge": 0.1664, "t3.2xlarge": 0.3328,
    "m5.large": 0.096,  "m5.xlarge": 0.192,  "m5.2xlarge": 0.384,
    "m5.4xlarge": 0.768, "m5.8xlarge": 1.536,
    "c5.xlarge": 0.17,  "c5.2xlarge": 0.34,  "c5.4xlarge": 0.68,
    "r5.large": 0.126,  "r5.xlarge": 0.252,  "r5.2xlarge": 0.504,
    "r5.4xlarge": 1.008, "r5.8xlarge": 2.016,
}


def _compute_oci_hourly(shape: str, ocpu: int, memory_gb: float) -> float:
    """Calculate OCI hourly cost for a given shape/config."""
    info = OCI_SHAPES.get(shape, OCI_SHAPES["VM.Standard.E4.Flex"])
    if "flat_rate_hour" in info:
        return info["flat_rate_hour"]
    return ocpu * info["per_ocpu_hour"] + memory_gb * info["per_gb_ram_hour"]


class SizingServer:
    SERVER_NAME = "sizing"
    VERSION = "2.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0.0

    def _record(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    # ------------------------------------------------------------------
    def estimate_compute(
        self,
        source_instance_type: str,
        source_provider: str = "AWS",
        workload_type: str = "general",
        rightsizing_factor: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Map a source instance type to the best OCI shape.

        Args:
            source_instance_type: e.g. 'm5.xlarge', 'Standard_D4s_v3', 'n2-standard-4'
            source_provider: 'AWS' | 'Azure' | 'GCP' | 'On-Premises'
            workload_type: hint for shape selection
            rightsizing_factor: 0.5–1.5 to scale resource needs (e.g. 0.8 to right-size down)
        """
        t0 = time.time()
        provider = source_provider.upper()

        # Look up source spec
        lookup_key = source_instance_type.lower()
        if provider == "AWS":
            spec = AWS_TO_OCI.get(lookup_key)
        elif provider == "AZURE":
            spec = AZURE_TO_OCI.get(source_instance_type)  # Azure names are case-sensitive
            if not spec:
                spec = AZURE_TO_OCI.get(lookup_key)
        elif provider == "GCP":
            spec = GCP_TO_OCI.get(lookup_key)
        else:
            spec = None  # On-Premises: use workload_type heuristic

        if spec:
            ocpu      = max(1, round(spec["ocpu"] * rightsizing_factor))
            memory_gb = max(1, round(spec["memory_gb"] * rightsizing_factor, 1))
            shape     = spec.get("shape", "VM.Standard.E4.Flex")
            wtype     = spec.get("workload", workload_type)
            note      = spec.get("note", "")
        else:
            # Fallback: pick best shape by workload_type
            wtype     = workload_type
            ocpu      = 2
            memory_gb = 16
            candidates = WORKLOAD_SHAPE_MATRIX.get(wtype, WORKLOAD_SHAPE_MATRIX["general"])
            shape     = candidates[0]
            note      = f"Instance '{source_instance_type}' not in lookup table — defaults applied"

        # Find best alternative shapes for the same workload
        candidates = WORKLOAD_SHAPE_MATRIX.get(wtype, WORKLOAD_SHAPE_MATRIX["general"])
        alternatives = [s for s in candidates if s != shape][:2]

        # Calculate costs
        oci_hourly   = _compute_oci_hourly(shape, ocpu, memory_gb)
        oci_monthly  = round(oci_hourly * 730, 2)
        oci_annually = round(oci_monthly * 12, 2)

        # Compare with source
        src_hourly  = AWS_PRICING.get(lookup_key, 0.0) if provider == "AWS" else 0.0
        src_monthly = round(src_hourly * 730, 2)
        savings_pct = round((1 - oci_monthly / max(src_monthly, 0.01)) * 100, 1) if src_monthly else None

        self._record((time.time() - t0) * 1000)
        return {
            "source_instance": source_instance_type,
            "source_provider": source_provider,
            "recommended_shape": shape,
            "ocpu": ocpu,
            "memory_gb": memory_gb,
            "workload_type": wtype,
            "oci_hourly_cost_usd": round(oci_hourly, 4),
            "oci_monthly_cost_usd": oci_monthly,
            "oci_annual_cost_usd": oci_annually,
            "source_monthly_cost_usd": src_monthly if src_monthly else "N/A",
            "estimated_savings_pct": savings_pct,
            "alternative_shapes": alternatives,
            "shape_details": {k: v for k, v in OCI_SHAPES[shape].items()
                              if k not in ("per_ocpu_hour", "per_gb_ram_hour")},
            "confidence": 0.95 if spec else 0.70,
            "note": note,
            "rightsizing_factor": rightsizing_factor,
        }

    # ------------------------------------------------------------------
    def estimate_storage(
        self,
        storage_type: str,
        size_gb: float,
        iops: Optional[int] = None,
        throughput_mbps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Map source storage type to OCI storage service."""
        t0 = time.time()
        stype = storage_type.lower()

        # Storage type → OCI service
        mapping = {
            # Object / Blob
            "s3":          ("Object Storage Standard",          0.0255),
            "blob":        ("Object Storage Standard",          0.0255),
            "gcs":         ("Object Storage Standard",          0.0255),
            "object":      ("Object Storage Standard",          0.0255),
            "glacier":     ("Archive Storage",                  0.0026),
            "s3-glacier":  ("Archive Storage",                  0.0026),
            "coldline":    ("Archive Storage",                  0.0026),
            "nearline":    ("Object Storage Infrequent Access", 0.01),
            # Block
            "ebs":         ("Block Volume",                     0.0255),
            "managed-disk":("Block Volume",                     0.0255),
            "persistent-disk":("Block Volume",                  0.0255),
            "block":       ("Block Volume",                     0.0255),
            # File
            "efs":         ("File Storage",                     0.07),
            "azure-files": ("File Storage",                     0.07),
            "filestore":   ("File Storage",                     0.07),
            "file":        ("File Storage",                     0.07),
            "nfs":         ("File Storage",                     0.07),
        }
        oci_service, rate = mapping.get(stype, ("Object Storage Standard", 0.0255))
        monthly_cost = round(size_gb * rate, 2)

        # Block volume IOPS guidance
        vpu_needed = None
        if oci_service == "Block Volume" and iops:
            # OCI: 10 VPU/GB → ~2000 IOPS per TB
            # Formula: IOPS = (VPU * size_gb) / 0.5  (approx)
            vpu_needed = min(120, max(10, round((iops / (size_gb * 2)) * 10)))
            extra_cost = size_gb * vpu_needed * 0.0017
            monthly_cost = round(monthly_cost + extra_cost, 2)

        self._record((time.time() - t0) * 1000)
        return {
            "source_storage_type": storage_type,
            "size_gb": size_gb,
            "oci_service": oci_service,
            "rate_per_gb_month": rate,
            "monthly_cost_usd": monthly_cost,
            "annual_cost_usd": round(monthly_cost * 12, 2),
            "recommended_vpu": vpu_needed,
            "confidence": 0.92,
        }

    # ------------------------------------------------------------------
    def estimate_network(
        self,
        monthly_data_transfer_gb: float = 0.0,
        num_load_balancers: int = 0,
        lb_type: str = "flexible",
    ) -> Dict[str, Any]:
        """Estimate OCI network monthly cost."""
        t0 = time.time()

        # Tiered egress
        first_10tb = min(monthly_data_transfer_gb, 10_000)
        next_40tb  = max(min(monthly_data_transfer_gb - 10_000, 40_000), 0)
        over_150tb = max(monthly_data_transfer_gb - 150_000, 0)
        egress_cost = first_10tb * 0.0085 + next_40tb * 0.0051 + over_150tb * 0.0026

        lb_hourly = 0.025 if lb_type == "flexible" else 0.008
        lb_cost = num_load_balancers * lb_hourly * 730

        total = egress_cost + lb_cost
        self._record((time.time() - t0) * 1000)
        return {
            "monthly_data_transfer_gb": monthly_data_transfer_gb,
            "num_load_balancers": num_load_balancers,
            "lb_type": lb_type,
            "egress_cost_usd": round(egress_cost, 2),
            "lb_cost_usd": round(lb_cost, 2),
            "total_monthly_cost_usd": round(total, 2),
            "total_annual_cost_usd": round(total * 12, 2),
            "confidence": 0.88,
        }

    # ------------------------------------------------------------------
    def recommend_shape(
        self,
        workload_type: str,
        min_ocpu: int = 1,
        min_memory_gb: int = 4,
        prefer_arm: bool = False,
    ) -> Dict[str, Any]:
        """Recommend OCI shapes for a given workload profile."""
        t0 = time.time()
        candidates = list(WORKLOAD_SHAPE_MATRIX.get(workload_type, WORKLOAD_SHAPE_MATRIX["general"]))
        if prefer_arm and "VM.Standard.A1.Flex" not in candidates:
            candidates.insert(0, "VM.Standard.A1.Flex")

        results = []
        for shape in candidates[:3]:
            info = OCI_SHAPES.get(shape, {})
            ocpu = max(min_ocpu, 2)
            mem  = max(min_memory_gb, 8)
            hourly = _compute_oci_hourly(shape, ocpu, mem)
            results.append({
                "shape": shape,
                "ocpu": ocpu,
                "memory_gb": mem,
                "hourly_cost_usd": round(hourly, 4),
                "monthly_cost_usd": round(hourly * 730, 2),
                "processor": info.get("processor", ""),
                "arch": info.get("arch", "x86_64"),
                "description": info.get("description", ""),
            })

        self._record((time.time() - t0) * 1000)
        return {
            "workload_type": workload_type,
            "recommendations": results,
            "primary": results[0] if results else None,
        }

    # ------------------------------------------------------------------
    def list_shapes(self) -> Dict[str, Any]:
        """Return full OCI shape catalogue."""
        return {"shapes": OCI_SHAPES, "count": len(OCI_SHAPES)}

    # ------------------------------------------------------------------
    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
            "status": "healthy",
            "aws_mappings": len(AWS_TO_OCI),
            "azure_mappings": len(AZURE_TO_OCI),
            "gcp_mappings": len(GCP_TO_OCI),
        }


sizing_server = SizingServer()
